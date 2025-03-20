from mem0 import Memory
from mem0.configs.base import MemoryConfig
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from ten.async_ten_env import AsyncTenEnv  # type: ignore


class AsyncMemory:
    """为本地 Memory 类提供混合同步/异步接口的包装器
    
    这个类接受配置参数，内部初始化 Memory 实例，
    提供以下功能：
    1. 查询接口(search, get, get_all)保持同步调用方式
    2. 写入/修改接口(add, update, delete等)提供异步调用方式
    3. 资源管理和错误处理
    
    适合作为独立的记忆模块对外提供服务。
    """
    
    def __init__(self, ten_env: AsyncTenEnv, config:MemoryConfig, max_workers=5, loop=None):
        """初始化包装器
        
        Args:
            ten_env (AsyncTenEnv): TEN环境对象，用于日志记录
            config (MemoryConfig): Memory 类的配置参数
            max_workers (int): 线程池的最大工作线程数
            loop (asyncio.AbstractEventLoop, optional): 要使用的事件循环，如果为None则使用当前线程的事件循环
        """
        self.ten_env = ten_env
        self.ten_env.log_info(f"AsyncMemory config:{config}")
        self.memory = Memory(config)  # 内部初始化 Memory 实例
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 设置标识参数
        self.user_id = None 
        self.agent_id = None 
        self.run_id = None
        
        # 使用外部提供的事件循环或获取当前线程的事件循环
        if loop is not None:
            self._loop = loop
        else:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                
        self.ten_env.log_info(f"AsyncMemoryWrapper 初始化成功，线程池大小: {max_workers}, 使用{'外部提供的' if loop else '自动获取的'}事件循环")
    
    @property
    def loop(self):
        """获取事件循环"""
        return self._loop
    
    # ================ 同步查询接口 ================
    
    def search(self, query, user_id=None, agent_id=None, run_id=None, limit=100, filters=None):
        """同步搜索记忆
        
        Args:
            query (str): 搜索查询文本
            user_id (str, optional): 用户ID过滤
            agent_id (str, optional): 代理ID过滤
            run_id (str, optional): 运行ID过滤
            limit (int, optional): 结果数量限制，默认100
            filters (dict, optional): 其他过滤条件
            
        Returns:
            dict: 搜索结果，包含匹配的记忆列表
        """
        start_time = time.time()
        
        self.ten_env.log_info(f"搜索记忆: query='{query[:50]}...', user_id={user_id}, limit={limit}")
        
        try:
            results = self.memory.search(query, user_id, agent_id, run_id, limit, filters)
            elapsed = time.time() - start_time
            self.ten_env.log_info(f"搜索记忆完成，找到{len(results.get('results', []))}条结果，耗时{elapsed:.3f}秒")
            
            # 记录找到的记忆详情
            if results and 'results' in results and results['results']:
                for i, entry in enumerate(results['results']):
                    memory_id = entry.get('id', f'未知_{i}')
                    memory_text = entry.get('memory', '无内容')
                    memory_score = entry.get('score', 0)
                    self.ten_env.log_info(f"{'='*40}")
                    self.ten_env.log_info(f"记忆 ID: {memory_id}")
                    self.ten_env.log_info(f"记忆内容: {memory_text[:100]}..." if len(memory_text) > 100 else f"记忆内容: {memory_text}")
                    self.ten_env.log_info(f"相关度分数: {memory_score:.4f}")
                    self.ten_env.log_info(f"用户: {entry.get('user_id', 'N/A')}")
                    self.ten_env.log_info(f"创建时间: {entry.get('created_at', 'N/A')}")
                    self.ten_env.log_info(f"更新时间: {entry.get('updated_at', 'N/A')}")
                    if 'metadata' in entry:
                        self.ten_env.log_info(f"元数据: {entry['metadata']}")
                self.ten_env.log_info(f"{'='*40}")
            
            return results
        except Exception as e:
            elapsed = time.time() - start_time
            self.ten_env.log_error(f"搜索记忆时出错: {e}，耗时{elapsed:.3f}秒")
            return {"results": [], "error": str(e)}
    
    def get(self, memory_id):
        """同步获取特定记忆
        
        Args:
            memory_id (str): 记忆的ID
            
        Returns:
            dict: 获取的记忆详情
        """
        start_time = time.time()
        self.ten_env.log_info(f"获取记忆: memory_id={memory_id}")
        
        try:
            result = self.memory.get(memory_id)
            elapsed = time.time() - start_time
            self.ten_env.log_info(f"获取记忆完成，耗时{elapsed:.3f}秒")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            self.ten_env.log_error(f"获取记忆 {memory_id} 时出错: {e}，耗时{elapsed:.3f}秒")
            return {"error": str(e)}
    
    def get_all(self, user_id=None, agent_id=None, run_id=None, limit=100):
        """同步获取所有记忆
        
        Args:
            user_id (str, optional): 用户ID过滤
            agent_id (str, optional): 代理ID过滤
            run_id (str, optional): 运行ID过滤
            limit (int, optional): 结果数量限制，默认100
            
        Returns:
            dict: 包含记忆列表的结果
        """
        start_time = time.time()
        self.ten_env.log_info(f"获取所有记忆: user_id={user_id}, limit={limit}")
        
        try:
            results = self.memory.get_all(user_id, agent_id, run_id, limit)
            elapsed = time.time() - start_time
            self.ten_env.log_info(f"获取所有记忆完成，找到{len(results.get('results', []))}条结果，耗时{elapsed:.3f}秒")
            return results
        except Exception as e:
            elapsed = time.time() - start_time
            self.ten_env.log_error(f"获取所有记忆时出错: {e}，耗时{elapsed:.3f}秒")
            return {"results": [], "error": str(e)}
    
    # ================ 异步修改接口 ================
    
    async def add(self, messages, user_id=None, agent_id=None, run_id=None, metadata=None, filters=None, prompt=None):
        """异步添加记忆
        
        Args:
            messages (list): 消息列表，每个消息包含角色和内容
            user_id (str, optional): 用户ID
            agent_id (str, optional): 代理ID
            run_id (str, optional): 运行ID
            metadata (dict, optional): 元数据
            filters (dict, optional): 过滤条件
            prompt (str, optional): 提示文本
            
        Returns:
            dict: 添加记忆操作的结果
        """
        start_time = time.time()
        
        # 记录消息内容的摘要
        messages_summary = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if isinstance(content, str):
                content_preview = content[:50] + ('...' if len(content) > 50 else '')
                messages_summary.append(f"{role}: {content_preview}")
            else:
                messages_summary.append(f"{role}: <non-text content>")
        
        self.ten_env.log_info(f"添加记忆: user_id={user_id}, messages=[{', '.join(messages_summary)}]")
        
        try:
            result = await self.loop.run_in_executor(
                self.executor, 
                lambda: self.memory.add(
                    messages=messages, 
                    user_id=user_id, 
                    agent_id=agent_id, 
                    run_id=run_id, 
                    metadata=metadata, 
                    filters=filters, 
                    prompt=prompt
                )
            )
            elapsed = time.time() - start_time
            self.ten_env.log_info(f"添加记忆完成，ID={result.get('id', 'N/A')}，耗时{elapsed:.3f}秒")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            self.ten_env.log_error(f"异步添加记忆时出错: {e}，耗时{elapsed:.3f}秒")
            return {"error": str(e)}
    
    async def update(self, memory_id, data):
        """异步更新记忆
        
        Args:
            memory_id (str): 要更新的记忆ID
            data (dict): 更新的数据
            
        Returns:
            dict: 更新结果
        """
        start_time = time.time()
        self.ten_env.log_info(f"更新记忆: memory_id={memory_id}")
        
        try:
            result = await self.loop.run_in_executor(
                self.executor, 
                lambda: self.memory.update(memory_id, data)
            )
            elapsed = time.time() - start_time
            self.ten_env.log_info(f"更新记忆完成，耗时{elapsed:.3f}秒")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            self.ten_env.log_error(f"异步更新记忆 {memory_id} 时出错: {e}，耗时{elapsed:.3f}秒")
            return {"error": str(e)}
    
    async def delete(self, memory_id):
        """异步删除记忆
        
        Args:
            memory_id (str): 要删除的记忆ID
            
        Returns:
            dict: 删除结果
        """
        start_time = time.time()
        self.ten_env.log_info(f"删除记忆: memory_id={memory_id}")
        
        try:
            result = await self.loop.run_in_executor(
                self.executor, 
                lambda: self.memory.delete(memory_id)
            )
            elapsed = time.time() - start_time
            self.ten_env.log_info(f"删除记忆完成，耗时{elapsed:.3f}秒")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            self.ten_env.log_error(f"异步删除记忆 {memory_id} 时出错: {e}，耗时{elapsed:.3f}秒")
            return {"error": str(e)}
    
    async def delete_all(self, user_id=None, agent_id=None, run_id=None):
        """异步删除所有符合条件的记忆
        
        Args:
            user_id (str, optional): 用户ID过滤
            agent_id (str, optional): 代理ID过滤
            run_id (str, optional): 运行ID过滤
            
        Returns:
            dict: 删除结果
        """
        start_time = time.time()
        
        self.ten_env.log_info(f"删除所有记忆: user_id={user_id}")
        
        try:
            result = await self.loop.run_in_executor(
                self.executor, 
                lambda: self.memory.delete_all(user_id, agent_id, run_id)
            )
            elapsed = time.time() - start_time
            self.ten_env.log_info(f"删除所有记忆完成，耗时{elapsed:.3f}秒")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            self.ten_env.log_error(f"异步删除所有记忆时出错: {e}，耗时{elapsed:.3f}秒")
            return {"error": str(e)}
    
    async def history(self, memory_id):
        """异步获取记忆历史
        
        Args:
            memory_id (str): 记忆ID
            
        Returns:
            list: 记忆的历史变更记录
        """
        start_time = time.time()
        self.ten_env.log_info(f"获取记忆历史: memory_id={memory_id}")
        
        try:
            result = await self.loop.run_in_executor(
                self.executor, 
                lambda: self.memory.history(memory_id)
            )
            elapsed = time.time() - start_time
            self.ten_env.log_info(f"获取记忆历史完成，耗时{elapsed:.3f}秒")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            self.ten_env.log_error(f"异步获取记忆 {memory_id} 历史时出错: {e}，耗时{elapsed:.3f}秒")
            return {"error": str(e)}
    
    async def reset(self):
        """异步重置记忆存储
        
        Returns:
            dict: 重置结果
        """
        start_time = time.time()
        self.ten_env.log_info("重置记忆存储")
        
        try:
            result = await self.loop.run_in_executor(
                self.executor, 
                lambda: self.memory.reset()
            )
            elapsed = time.time() - start_time
            self.ten_env.log_info(f"重置记忆存储完成，耗时{elapsed:.3f}秒")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            self.ten_env.log_error(f"异步重置记忆存储时出错: {e}，耗时{elapsed:.3f}秒")
            return {"error": str(e)}
    
    # ================ 资源管理 ================
    
    def close(self):
        """关闭执行器，释放资源
        在程序退出前应当调用此方法
        """
        try:
            self.executor.shutdown(wait=False)
            self.ten_env.log_info("AsyncMemoryWrapper 资源已释放")
        except Exception as e:
            self.ten_env.log_error(f"关闭资源时出错: {e}")
    
    def __enter__(self):
        """支持上下文管理器协议"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议，退出时自动释放资源"""
        self.close()

    # ============ 为了与原有MemoryManager兼容添加的接口 ============
    
    async def initialize(self, user_id=None, agent_id=None, run_id=None):
        """初始化记忆管理器，保持与MemoryManager接口兼容"""
        start_time = time.time()
        self.ten_env.log_info("AsyncMemoryWrapper 初始化...")
        # 设置标识参数
        self.user_id = user_id 
        self.agent_id = agent_id 
        self.run_id = run_id
        try:                   
            # 尝试获取所有记忆，检查是否能够正常工作
            self.get_all(user_id=self.user_id, agent_id=self.agent_id, run_id=self.run_id, limit=100)
            
            elapsed = time.time() - start_time
            self.ten_env.log_info(f"AsyncMemoryWrapper 初始化成功，耗时{elapsed:.3f}秒")
            return True
        except Exception as e:
            elapsed = time.time() - start_time
            self.ten_env.log_error(f"AsyncMemoryWrapper 初始化失败: {e}，耗时{elapsed:.3f}秒")
            return False
            
    async def search_memories(self, query, limit=5):
        """搜索相关记忆，保持与MemoryManager接口兼容"""
        results = self.search(
            query, 
            user_id=self.user_id,
            agent_id=self.agent_id,
            run_id=self.run_id,
            limit=limit
        )
        if "error" in results:
            return []
        return results.get("results", [])
        
    async def store_memory(self,user_message, assistant_message, metadata=None):
        """存储对话记忆，保持与MemoryManager接口兼容"""
        start_time = time.time()
        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message}
        ]
        
        result = await self.add(
            messages=messages, 
            user_id=self.user_id,
            agent_id=self.agent_id,
            run_id=self.run_id,
            metadata=metadata or {}
        )
        
        elapsed = time.time() - start_time
        if "error" in result:
            self.ten_env.log_error(f"存储记忆失败: {result['error']}，耗时{elapsed:.3f}秒")
            return None
            
        memory_id = result.get("id")
        self.ten_env.log_info(f"存储记忆成功，ID={memory_id}，耗时{elapsed:.3f}秒")
        return memory_id
        
    async def clear_all_memories(self):
        """清除所有存储的记忆，保持与MemoryManager接口兼容"""
        start_time = time.time()
        self.ten_env.log_info("清除所有记忆(兼容接口)")
        
        result = await self.delete_all(
            user_id=self.user_id,
            agent_id=self.agent_id,
            run_id=self.run_id
        )
        
        elapsed = time.time() - start_time
        if "error" in result:
            self.ten_env.log_error(f"清除记忆失败: {result['error']}，耗时{elapsed:.3f}秒")
            return False
            
        self.ten_env.log_info(f"清除记忆成功，耗时{elapsed:.3f}秒")
        return True
        
    async def format_context(self, memories):
        """将记忆格式化为上下文字符串，保持与MemoryManager接口兼容"""
        if not memories:
            return ""
        return "\n".join(f"- {entry['memory']}" for entry in memories)


# 为MemoryManager保留原有的实现
class MemoryManager:
    """记忆管理器，提供对话记忆的存储和检索功能
    
    这个类作为对外接口，内部使用AsyncMemoryWrapper处理实际逻辑
    保持与旧版MemoryManager兼容的接口，简化集成
    """
    
    def __init__(self, async_ten_env: AsyncTenEnv, memory: AsyncMemory):
        """初始化记忆管理器
        
        Args:
            async_ten_env: TEN环境对象
            config: memory 的config
        """
        # 初始化内部包装器
        self.async_ten_env = async_ten_env
        self.memory_delegate = memory
        # 设置标识参数
        self.user_id = None 
        self.agent_id = None 
        self.run_id = None
        
    async def initialize(self, user_id: str = None, agent_id: str = None, run_id: str = None):
        """初始化记忆管理器
        
        Args:
            user_id: 用户标识（可选）
            agent_id: 代理标识（可选）
            run_id: 会话标识（可选）
            
        Returns:
            bool: 初始化是否成功
        """
        start_time = time.time()
        self.async_ten_env.log_info("正在初始化记忆管理器...")

        # 设置标识参数
        self.user_id = user_id 
        self.agent_id = agent_id 
        self.run_id = run_id
        if user_id is None:
            self.async_ten_env.log_error(f"ser_id is None")
            return
        
        self.async_ten_env.log_info(f"记忆标识: user_id={self.user_id}, agent_id={self.agent_id}, run_id={self.run_id}")
        
        try:
            # 测试连接
            await self.memory_delegate.initialize(user_id=self.user_id,agent_id=self.agent_id,run_id=self.run_id)
            elapsed = time.time() - start_time
            self.async_ten_env.log_info(f"记忆管理器初始化成功，耗时{elapsed:.3f}秒")
            return True
            
        except Exception as e:
            elapsed = time.time() - start_time
            self.async_ten_env.log_error(f"记忆管理器初始化失败: {e}，耗时{elapsed:.3f}秒")
            return False
    
    async def search_memories(self, query: str, limit: int = 5):
        """搜索相关记忆
        
        Args:
            query: 搜索查询词
            limit: 结果数量限制
            
        Returns:
            list: 相关记忆列表
        """
        if not self.memory_delegate:
            self.async_ten_env.log_error("记忆管理器未初始化")
            return []
            
        return await self.memory_delegate.search_memories(query, limit)
    
    async def store_memory(self, user_message: str, assistant_message: str, metadata: dict = None):
        """存储对话记忆
        
        Args:
            prompt: 系统prompt
            user_message: 用户消息
            assistant_message: 助手回复
            metadata: 记忆元数据（可选）
            
        Returns:
            str: 记忆ID，如果存储失败则返回None
        """
        if not self.memory_delegate:
            self.async_ten_env.log_error("记忆管理器未初始化")
            return None
            
        return await self.memory_delegate.store_memory(user_message, assistant_message, metadata)
    
    async def clear_all_memories(self):
        """清除所有记忆
        
        Returns:
            bool: 操作是否成功
        """
        if not self.memory_delegate:
            self.async_ten_env.log_error("记忆管理器未初始化")
            return False
            
        return await self.memory_delegate.clear_all_memories()
    
    async def format_context(self, memories):
        """将记忆格式化为上下文
        
        Args:
            memories: 记忆列表
            
        Returns:
            str: 格式化后的上下文
        """
        if not self.memory_delegate:
            self.async_ten_env.log_error("记忆管理器未初始化")
            return ""
            
        return await self.memory_delegate.format_context(memories)
        
    def close(self):
        """关闭记忆管理器并释放资源"""
        if self.memory_delegate:
            self.memory_delegate.close()
            self.async_ten_env.log_info("记忆管理器已关闭")
            self.memory_delegate = None