from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import (DistanceMethodEnums, PgVectorTableSchemeEnums, 
                             PgVectorDistanceMethodEnums, PgVectorIndexTypeEnums)
import logging
from typing import List
from models.db_schemas import RetrievedDocument
from sqlalchemy.sql import text as sql_text
import json
import re


# Vector collections are always named `collection_{vector_size}_{project_id}`
# (both integers — see NLPController.create_collection_name). A table/index name
# is an SQL identifier, so it cannot be a bind parameter and must be interpolated
# into the DDL/DML below. Validate it as a tripwire before it ever reaches SQL:
# in normal operation this never fails, but it stops a malformed or
# attacker-influenced name from becoming an injection vector (defence in depth).
_VALID_COLLECTION = re.compile(r'^collection_\d+_\d+$')


def _validate_collection(collection_name: str) -> str:
    if not isinstance(collection_name, str) or not _VALID_COLLECTION.match(collection_name):
        raise ValueError(f"Invalid vector collection name: {collection_name!r}")
    return collection_name


class PGVectorProvider(VectorDBInterface):

    def __init__(self, db_client, default_vector_size: int = 786,
                       distance_method: str = None, index_threshold: int=100):
        
        self.db_client = db_client
        self.default_vector_size = default_vector_size
        
        self.index_threshold = index_threshold

        if distance_method == DistanceMethodEnums.COSINE.value:
            distance_method = PgVectorDistanceMethodEnums.COSINE.value
        elif distance_method == DistanceMethodEnums.DOT.value:
            distance_method = PgVectorDistanceMethodEnums.DOT.value

        self.pgvector_table_prefix = PgVectorTableSchemeEnums._PREFIX.value
        self.distance_method = distance_method

        self.logger = logging.getLogger("uvicorn")
        self.default_index_name = lambda collection_name: f"{collection_name}_vector_idx"


    async def connect(self):
        async with self.db_client() as session:
            async with session.begin():
                await session.execute(sql_text(
                    "CREATE EXTENSION IF NOT EXISTS vector"
                ))
                await session.commit()

    async def disconnect(self):
        pass

    async def is_collection_existed(self, collection_name: str) -> bool:
        _validate_collection(collection_name)

        record = None
        async with self.db_client() as session:
            async with session.begin():
                list_tbl = sql_text(f'SELECT * FROM pg_tables WHERE tablename = :collection_name')
                results = await session.execute(list_tbl, {"collection_name": collection_name})
                record = results.scalar_one_or_none()

        return record is not None
    
    async def list_all_collections(self) -> List:
        records = []
        async with self.db_client() as session:
            async with session.begin():
                list_tbl = sql_text('SELECT tablename FROM pg_tables WHERE tablename LIKE :prefix')
                results = await session.execute(list_tbl, {"prefix": self.pgvector_table_prefix})
                records = results.scalars().all()
        
        return records
    
    async def get_collection_info(self, collection_name: str) -> dict:
        _validate_collection(collection_name)
        async with self.db_client() as session:
            async with session.begin():
                
                table_info_sql = sql_text(f'''
                    SELECT schemaname, tablename, tableowner, tablespace, hasindexes 
                    FROM pg_tables 
                    WHERE tablename = :collection_name
                ''')

                table_info = await session.execute(table_info_sql, {"collection_name": collection_name})
                table_data = table_info.fetchone()
                
                if not table_data:
                    return None
                
                # Only execute COUNT if the table actually exists
                count_sql = sql_text(f'SELECT COUNT(*) FROM {collection_name}')
                record_count = await session.execute(count_sql)
                
                return {
                    "table_info": {
                        "schemaname": table_data[0],
                        "tablename": table_data[1],
                        "tableowner": table_data[2],
                        "tablespace": table_data[3],
                        "hasindexes": table_data[4],
                    },
                    "record_count": record_count.scalar_one(),
                }
            
    async def delete_collection(self, collection_name: str):
        _validate_collection(collection_name)
        async with self.db_client() as session:
            async with session.begin():
                self.logger.info(f"Deleting collection: {collection_name}")

                delete_sql = sql_text(f'DROP TABLE IF EXISTS {collection_name}')
                await session.execute(delete_sql)
                await session.commit()
        
        return True

    async def create_collection(self, collection_name: str,
                                      embedding_size: int,
                                      do_reset: bool = False):
        
        if do_reset:
            _ = await self.delete_collection(collection_name=collection_name)

        is_collection_existed = await self.is_collection_existed(collection_name=collection_name)
        if not is_collection_existed:
            self.logger.info(f"Creating collection: {collection_name}")
            async with self.db_client() as session:
                async with session.begin():
                    # Ensure extensions are available
                    await session.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector"))
                    await session.execute(sql_text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

                    create_sql = sql_text(
                        f'CREATE TABLE {collection_name} ('
                            f'{PgVectorTableSchemeEnums.ID.value} bigserial PRIMARY KEY,'
                            f'{PgVectorTableSchemeEnums.TEXT.value} text, '
                            f'{PgVectorTableSchemeEnums.VECTOR.value} vector({embedding_size}), '
                            f'{PgVectorTableSchemeEnums.METADATA.value} jsonb DEFAULT \'{{}}\', '
                            f'{PgVectorTableSchemeEnums.CHUNK_ID.value} integer, '
                            f'FOREIGN KEY ({PgVectorTableSchemeEnums.CHUNK_ID.value}) REFERENCES chunks(chunk_id)'
                        ')'
                    )
                    await session.execute(create_sql)
                    
                    # Create HNSW index for high-speed vector search
                    self.logger.info(f"Creating HNSW vector index for collection: {collection_name}")
                    vector_idx_sql = sql_text(
                        f"CREATE INDEX IF NOT EXISTS {collection_name}_vector_idx ON {collection_name} "
                        f"USING hnsw ({PgVectorTableSchemeEnums.VECTOR.value} vector_cosine_ops)"
                    )
                    await session.execute(vector_idx_sql)

                    # Create GIN index for smart text/keyword search (using Trigrams for Arabic support)
                    self.logger.info(f"Creating GIN trigram index for collection: {collection_name}")
                    text_idx_sql = sql_text(
                        f"CREATE INDEX IF NOT EXISTS {collection_name}_text_trgm_idx ON {collection_name} "
                        f"USING GIN ({PgVectorTableSchemeEnums.TEXT.value} gin_trgm_ops)"
                    )
                    await session.execute(text_idx_sql)
                    
                    await session.commit()
            
            return True

        return False
    
    async def is_index_existed(self, collection_name: str) -> bool:
        index_name = self.default_index_name(collection_name)
        async with self.db_client() as session:
            async with session.begin():
                check_sql = sql_text(f""" 
                                    SELECT 1 
                                    FROM pg_indexes 
                                    WHERE tablename = :collection_name
                                    AND indexname = :index_name
                                    """)
                results = await session.execute(check_sql, {"collection_name": collection_name, "index_name": index_name})
                
                return bool(results.scalar_one_or_none())
            
    async def create_vector_index(self, collection_name: str,
                                        index_type: str = PgVectorIndexTypeEnums.HNSW.value):
        _validate_collection(collection_name)
        is_index_existed = await self.is_index_existed(collection_name=collection_name)
        if is_index_existed:
            return False
        
        async with self.db_client() as session:
            async with session.begin():
                count_sql = sql_text(f'SELECT COUNT(*) FROM {collection_name}')
                result = await session.execute(count_sql)
                records_count = result.scalar_one()

                if records_count < self.index_threshold:
                    return False
                
                self.logger.info(f"START: Creating vector index for collection: {collection_name}")
                
                index_name = self.default_index_name(collection_name)
                create_idx_sql = sql_text(
                                            f'CREATE INDEX {index_name} ON {collection_name} '
                                            f'USING {index_type} ({PgVectorTableSchemeEnums.VECTOR.value} {self.distance_method})'
                                          )

                await session.execute(create_idx_sql)

                self.logger.info(f"END: Created vector index for collection: {collection_name}")

    async def reset_vector_index(self, collection_name: str, 
                                       index_type: str = PgVectorIndexTypeEnums.HNSW.value) -> bool:

        _validate_collection(collection_name)
        index_name = self.default_index_name(collection_name)
        async with self.db_client() as session:
            async with session.begin():
                drop_sql = sql_text(f'DROP INDEX IF EXISTS {index_name}')
                await session.execute(drop_sql)
        
        return await self.create_vector_index(collection_name=collection_name, index_type=index_type)

    
    async def insert_one(self, collection_name: str, text: str, vector: list,
                            metadata: dict = None,
                            record_id: str = None):
        
        is_collection_existed = await self.is_collection_existed(collection_name=collection_name)
        if not is_collection_existed:
            self.logger.error(f"Can not insert new record to non-existed collection: {collection_name}")
            return False
        
        if not record_id:
            self.logger.error(f"Can not insert new record without chunk_id: {collection_name}")
            return False
        
        async with self.db_client() as session:
            async with session.begin():
                insert_sql = sql_text(f'INSERT INTO {collection_name} '
                                      f'({PgVectorTableSchemeEnums.TEXT.value}, {PgVectorTableSchemeEnums.VECTOR.value}, {PgVectorTableSchemeEnums.METADATA.value}, {PgVectorTableSchemeEnums.CHUNK_ID.value}) '
                                      'VALUES (:text, :vector, :metadata, :chunk_id)'
                                      )
                
                metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata is not None else "{}"
                await session.execute(insert_sql, {
                    'text': text,
                    'vector': "[" + ",".join([ str(v) for v in vector ]) + "]",
                    'metadata': metadata_json,
                    'chunk_id': record_id
                })
                await session.commit()

                await self.create_vector_index(collection_name=collection_name)
        
        return True
    

    async def insert_many(self, collection_name: str, texts: list,
                         vectors: list, metadata: list = None,
                         record_ids: list = None, batch_size: int = 50):
        
        is_collection_existed = await self.is_collection_existed(collection_name=collection_name)
        if not is_collection_existed:
            self.logger.error(f"Can not insert new records to non-existed collection: {collection_name}")
            return False
        
        if len(vectors) != len(record_ids):
            self.logger.error(f"Invalid data items for collection: {collection_name}")
            return False
        
        if not metadata or len(metadata) == 0:
            metadata = [None] * len(texts)
        
        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i:i+batch_size]
                    batch_vectors = vectors[i:i + batch_size]
                    batch_metadata = metadata[i:i + batch_size]
                    batch_record_ids = record_ids[i:i + batch_size]

                    values = []

                    for _text, _vector, _metadata, _record_id in zip(batch_texts, batch_vectors, batch_metadata, batch_record_ids):
                        
                        metadata_json = json.dumps(_metadata, ensure_ascii=False) if _metadata is not None else "{}"
                        values.append({
                            'text': _text,
                            'vector': "[" + ",".join([ str(v) for v in _vector ]) + "]",
                            'metadata': metadata_json,
                            'chunk_id': _record_id
                        })
                    
                    batch_insert_sql = sql_text(f'INSERT INTO {collection_name} '
                                    f'({PgVectorTableSchemeEnums.TEXT.value}, '
                                    f'{PgVectorTableSchemeEnums.VECTOR.value}, '
                                    f'{PgVectorTableSchemeEnums.METADATA.value}, '
                                    f'{PgVectorTableSchemeEnums.CHUNK_ID.value}) '
                                    f'VALUES (:text, :vector, :metadata, :chunk_id)')
                    
                    await session.execute(batch_insert_sql, values)

        await self.create_vector_index(collection_name=collection_name)

        return True
    
    async def search_by_vector(self, collection_name: str, vector: list, limit: int):

        is_collection_existed = await self.is_collection_existed(collection_name=collection_name)
        if not is_collection_existed:
            self.logger.error(f"Can not search for records in a non-existed collection: {collection_name}")
            return False
        
        vector = "[" + ",".join([ str(v) for v in vector ]) + "]"
        async with self.db_client() as session:
            async with session.begin():
                search_sql = sql_text(f'SELECT {PgVectorTableSchemeEnums.TEXT.value} as text, 1 - ({PgVectorTableSchemeEnums.VECTOR.value} <=> :vector) as score'
                                      f' FROM {collection_name}'
                                      ' ORDER BY score DESC '
                                      'LIMIT :limit'
                                      )

                result = await session.execute(search_sql, {"vector": vector, "limit": limit})

                records = result.fetchall()

                return [
                    RetrievedDocument(
                        text=record.text,
                        score=record.score
                    )
                    for record in records
                ]

    async def search_by_text(self, collection_name: str, query: str, limit: int):
        
        is_collection_existed = await self.is_collection_existed(collection_name=collection_name)
        if not is_collection_existed:
            self.logger.error(f"Can not search for records in a non-existed collection: {collection_name}")
            return False
            
        async with self.db_client() as session:
            async with session.begin():
                # Using pg_trgm similarity for better Arabic/fuzzy keyword matching
                search_sql = sql_text(f"""
                    SELECT {PgVectorTableSchemeEnums.TEXT.value} as text, 
                           similarity({PgVectorTableSchemeEnums.TEXT.value}, :query) as score
                    FROM {collection_name}
                    WHERE {PgVectorTableSchemeEnums.TEXT.value} % :query
                    ORDER BY score DESC
                    LIMIT :limit
                """)

                result = await session.execute(search_sql, {"query": query, "limit": limit})
                records = result.fetchall()

                return [
                    RetrievedDocument(
                        text=record.text,
                        score=record.score
                    )
                    for record in records
                ]

    async def hybrid_search(self, collection_name: str, query: str, vector: list, limit: int = 10, over_fetch: int = 20):
        """
        Merges results from vector search and keyword search using Reciprocal Rank Fusion (RRF).
        """
        vector_results = await self.search_by_vector(collection_name, vector, over_fetch) or []
        text_results = await self.search_by_text(collection_name, query, over_fetch) or []
        
        # RRF Algorithm Implementation
        # k=60 is the standard constant used in RRF to balance ranking
        k = 60
        scores = {}
        doc_map = {}

        for rank, doc in enumerate(vector_results):
            doc_id = doc.text
            doc_map[doc_id] = doc
            scores[doc_id] = scores.get(doc_id, 0) + (1.0 / (k + rank + 1))
            
        for rank, doc in enumerate(text_results):
            doc_id = doc.text
            doc_map[doc_id] = doc
            scores[doc_id] = scores.get(doc_id, 0) + (1.0 / (k + rank + 1))
            
        # Sort by RRF score
        sorted_doc_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        final_results = []
        for doc_id in sorted_doc_ids[:limit]:
            doc = doc_map[doc_id]
            doc.score = scores[doc_id]
            final_results.append(doc)
            
        return final_results