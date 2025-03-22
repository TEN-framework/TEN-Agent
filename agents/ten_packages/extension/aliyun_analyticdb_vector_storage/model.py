# -*- coding: utf-8 -*-

from alibabacloud_gpdb20160503 import models as gpdb_20160503_models  # type: ignore
import time
import json
from typing import Dict, List, Any, Tuple
from alibabacloud_tea_util import models as util_models


class Model:
    def __init__(self, ten_env, region_id, dbinstance_id, client):
        self.region_id = region_id
        self.dbinstance_id = dbinstance_id
        self.client = client
        self.read_timeout = 10 * 1000
        self.connect_timeout = 10 * 1000
        self.ten_env = ten_env

    def get_client(self):
        return self.client.get()

    def init_vector_database(self, account, account_password) -> None:
        try:
            request = gpdb_20160503_models.InitVectorDatabaseRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                manager_account=account,
                manager_account_password=account_password,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = self.get_client().init_vector_database_with_options(
                request, runtime
            )
            self.ten_env.log_debug(
                f"init_vector_database response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e

    async def init_vector_database_async(self, account, account_password) -> None:
        try:
            request = gpdb_20160503_models.InitVectorDatabaseRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                manager_account=account,
                manager_account_password=account_password,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = await self.get_client().init_vector_database_with_options_async(
                request, runtime
            )
            self.ten_env.log_debug(
                f"init_vector_database response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e

    def create_namespace(
        self, account, account_password, namespace, namespace_password
    ) -> None:
        try:
            request = gpdb_20160503_models.CreateNamespaceRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                manager_account=account,
                manager_account_password=account_password,
                namespace=namespace,
                namespace_password=namespace_password,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = self.get_client().create_namespace_with_options(request, runtime)
            self.ten_env.log_debug(
                f"create_namespace response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e

    async def create_namespace_async(
        self, account, account_password, namespace, namespace_password
    ) -> None:
        try:
            request = gpdb_20160503_models.CreateNamespaceRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                manager_account=account,
                manager_account_password=account_password,
                namespace=namespace,
                namespace_password=namespace_password,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = await self.get_client().create_namespace_with_options_async(
                request, runtime
            )
            self.ten_env.log_debug(
                f"create_namespace response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e

    def create_collection(
        self,
        account,
        account_password,
        namespace,
        collection,
        parser: str = None,
        metrics: str = None,
        hnsw_m: int = None,
        pq_enable: int = None,
        external_storage: int = None,
    ) -> None:
        try:
            metadata = '{"update_ts": "bigint", "file_name": "text", "content": "text"}'
            full_text_retrieval_fields = "update_ts,file_name"
            request = gpdb_20160503_models.CreateCollectionRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                manager_account=account,
                manager_account_password=account_password,
                namespace=namespace,
                collection=collection,
                metadata=metadata,
                full_text_retrieval_fields=full_text_retrieval_fields,
                parser=parser,
                metrics=metrics,
                hnsw_m=hnsw_m,
                pq_enable=pq_enable,
                external_storage=external_storage,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = self.get_client().create_collection_with_options(
                request, runtime
            )
            self.ten_env.log_debug(
                f"create_document_collection response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e

    async def create_collection_async(
        self,
        account,
        account_password,
        namespace,
        collection,
        parser: str = None,
        metrics: str = None,
        hnsw_m: int = None,
        pq_enable: int = None,
        external_storage: int = None,
    ) -> None:
        try:
            metadata = '{"update_ts": "bigint", "file_name": "text", "content": "text"}'
            full_text_retrieval_fields = "update_ts,file_name"
            request = gpdb_20160503_models.CreateCollectionRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                manager_account=account,
                manager_account_password=account_password,
                namespace=namespace,
                collection=collection,
                metadata=metadata,
                full_text_retrieval_fields=full_text_retrieval_fields,
                parser=parser,
                metrics=metrics,
                hnsw_m=hnsw_m,
                pq_enable=pq_enable,
                external_storage=external_storage,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = await self.get_client().create_collection_with_options_async(
                request, runtime
            )
            self.ten_env.log_debug(
                f"create_document_collection response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e

    def delete_collection(self, namespace, namespace_password, collection) -> None:
        try:
            request = gpdb_20160503_models.DeleteCollectionRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                namespace_password=namespace_password,
                namespace=namespace,
                collection=collection,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = self.get_client().delete_collection_with_options(
                request, runtime
            )
            self.ten_env.log_debug(
                f"delete_collection response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e

    async def delete_collection_async(
        self, namespace, namespace_password, collection
    ) -> None:
        try:
            request = gpdb_20160503_models.DeleteCollectionRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                namespace_password=namespace_password,
                namespace=namespace,
                collection=collection,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = await self.get_client().delete_collection_with_options_async(
                request, runtime
            )
            self.ten_env.log_info(
                f"delete_collection response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e

    def upsert_collection_data(
        self,
        collection,
        namespace,
        namespace_password,
        rows: List[Tuple[str, str, List[float]]] = None,
    ) -> None:
        try:
            request_rows = []
            for row in rows:
                file_name = row[0]
                content = row[1]
                vector = row[2]
                metadata = {
                    "update_ts": int(time.time() * 1000),
                    "file_name": file_name,
                    "content": content,
                }
                request_row = gpdb_20160503_models.UpsertCollectionDataRequestRows(
                    metadata=metadata, vector=vector
                )
                request_rows.append(request_row)
            upsert_collection_data_request = (
                gpdb_20160503_models.UpsertCollectionDataRequest(
                    region_id=self.region_id,
                    dbinstance_id=self.dbinstance_id,
                    collection=collection,
                    namespace_password=namespace_password,
                    namespace=namespace,
                    rows=request_rows,
                )
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = self.get_client().upsert_collection_data_with_options(
                upsert_collection_data_request, runtime
            )
            self.ten_env.log_debug(
                f"upsert_collection response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e

    async def upsert_collection_data_async(
        self,
        collection,
        namespace,
        namespace_password,
        rows: List[Tuple[str, str, List[float]]] = None,
    ) -> None:
        try:
            request_rows = []
            for row in rows:
                file_name = row[0]
                content = row[1]
                vector = row[2]
                metadata = {
                    "update_ts": int(time.time() * 1000),
                    "file_name": file_name,
                    "content": content,
                }
                request_row = gpdb_20160503_models.UpsertCollectionDataRequestRows(
                    metadata=metadata, vector=vector
                )
                request_rows.append(request_row)
            upsert_collection_data_request = (
                gpdb_20160503_models.UpsertCollectionDataRequest(
                    region_id=self.region_id,
                    dbinstance_id=self.dbinstance_id,
                    collection=collection,
                    namespace_password=namespace_password,
                    namespace=namespace,
                    rows=request_rows,
                )
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = (
                await self.get_client().upsert_collection_data_with_options_async(
                    upsert_collection_data_request, runtime
                )
            )
            self.ten_env.log_debug(
                f"upsert_collection response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e

    # pylint: disable=redefined-builtin
    def query_collection_data(
        self,
        collection,
        namespace,
        namespace_password,
        vector: List[float] = None,
        top_k: int = 10,
        content: str = None,
        filter: str = None,
        hybrid_search: str = None,
        hybrid_search_args: Dict[str, dict] = None,
        include_metadata_fields: str = None,
        include_values: bool = None,
        metrics: str = None,
    ) -> Tuple[Any, Any]:
        try:
            query_collection_data_request = (
                gpdb_20160503_models.QueryCollectionDataRequest(
                    region_id=self.region_id,
                    dbinstance_id=self.dbinstance_id,
                    collection=collection,
                    namespace_password=namespace_password,
                    namespace=namespace,
                    vector=vector,
                    top_k=top_k,
                    content=content,
                    filter=filter,
                    hybrid_search=hybrid_search,
                    hybrid_search_args=hybrid_search_args,
                    include_metadata_fields=include_metadata_fields,
                    include_values=include_values,
                    metrics=metrics,
                )
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = self.get_client().query_collection_data_with_options(
                query_collection_data_request, runtime
            )
            self.ten_env.log_debug(
                f"query_collection response code: {response.status_code}"
            )
            return response, None
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return None, e

    # pylint: disable=redefined-builtin
    async def query_collection_data_async(
        self,
        collection,
        namespace,
        namespace_password,
        vector: List[float] = None,
        top_k: int = 10,
        content: str = None,
        filter: str = None,
        hybrid_search: str = None,
        hybrid_search_args: Dict[str, dict] = None,
        include_metadata_fields: str = None,
        include_values: bool = None,
        metrics: str = None,
    ) -> Tuple[Any, Any]:
        try:
            query_collection_data_request = (
                gpdb_20160503_models.QueryCollectionDataRequest(
                    region_id=self.region_id,
                    dbinstance_id=self.dbinstance_id,
                    collection=collection,
                    namespace_password=namespace_password,
                    namespace=namespace,
                    vector=vector,
                    top_k=top_k,
                    content=content,
                    filter=filter,
                    hybrid_search=hybrid_search,
                    hybrid_search_args=hybrid_search_args,
                    include_metadata_fields=include_metadata_fields,
                    include_values=include_values,
                    metrics=metrics,
                )
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = await self.get_client().query_collection_data_with_options_async(
                query_collection_data_request, runtime
            )
            self.ten_env.log_debug(
                f"query_collection response code: {response.status_code}"
            )
            return response, None
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return None, e

    def parse_collection_data(
        self, body: gpdb_20160503_models.QueryCollectionDataResponseBody
    ) -> str:
        try:
            matches = body.to_map()["Matches"]["match"]
            results = [
                {"content": match["Metadata"]["content"], "score": match["Score"]}
                for match in matches
            ]
            results.sort(key=lambda x: x["score"], reverse=True)
            json_str = json.dumps(results)
            return json_str
        except Exception as e:
            self.ten_env.log_error(
                f"parse collection data failed, error: {e}, data: {body.to_map()}"
            )
            return "[]"

    def list_collections(self, namespace, namespace_password) -> Tuple[List[str], Any]:
        try:
            request = gpdb_20160503_models.ListCollectionsRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                namespace=namespace,
                namespace_password=namespace_password,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = self.get_client().list_collections_with_options(request, runtime)
            self.ten_env.log_debug(
                f"list_collections response code: {response.status_code}, body:{response.body}"
            )
            collections = response.body.to_map()["Collections"]["collection"]
            return collections, None
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return [], e

    async def list_collections_async(
        self, namespace, namespace_password
    ) -> Tuple[List[str], Any]:
        try:
            request = gpdb_20160503_models.ListCollectionsRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                namespace=namespace,
                namespace_password=namespace_password,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = await self.get_client().list_collections_with_options_async(
                request, runtime
            )
            self.ten_env.log_debug(
                f"list_collections response code: {response.status_code}, body:{response.body}"
            )
            collections = response.body.to_map()["Collections"]["collection"]
            return collections, None
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return [], e

    def create_vector_index(
        self, account, account_password, namespace, collection, dimension
    ) -> None:
        try:
            request = gpdb_20160503_models.CreateVectorIndexRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                manager_account=account,
                manager_account_password=account_password,
                namespace=namespace,
                collection=collection,
                dimension=dimension,
                pq_enable=0,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = self.get_client().create_vector_index_with_options(
                request, runtime
            )
            self.ten_env.log_debug(
                f"create_vector_index response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e

    async def create_vector_index_async(
        self, account, account_password, namespace, collection, dimension
    ) -> None:
        try:
            request = gpdb_20160503_models.CreateVectorIndexRequest(
                region_id=self.region_id,
                dbinstance_id=self.dbinstance_id,
                manager_account=account,
                manager_account_password=account_password,
                namespace=namespace,
                collection=collection,
                dimension=dimension,
                pq_enable=0,
            )
            runtime = util_models.RuntimeOptions(
                read_timeout=self.read_timeout, connect_timeout=self.connect_timeout
            )
            response = await self.get_client().create_vector_index_with_options_async(
                request, runtime
            )
            self.ten_env.log_debug(
                f"create_vector_index response code: {response.status_code}, body:{response.body}"
            )
        except Exception as e:
            self.ten_env.log_error(f"Error: {e}")
            return e
