'use client';

import { useEffect, useRef, useState } from 'react';
import { Cog6ToothIcon } from '@heroicons/react/24/outline';
import Link from 'next/link';
import dynamic from 'next/dynamic';

// 动态导入 RTCComponent，但不显示加载状态
const RTCComponent = dynamic(() => import('@/components/RTCComponent'), {
  ssr: false,
  loading: () => null
});

export default function Home() {
  const staticVideoRef = useRef<HTMLVideoElement>(null);
  const dynamicVideoRef = useRef<HTMLVideoElement>(null);
  const [showRTC, setShowRTC] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isAudioActive, setIsAudioActive] = useState(false);
  const [isDynamicVideoReady, setIsDynamicVideoReady] = useState(false);

  // 初始化视频
  useEffect(() => {
    // 确保两个视频都加载完成
    const loadVideos = async () => {
      try {
        // 预加载静态视频
        if (staticVideoRef.current) {
          staticVideoRef.current.load();
          staticVideoRef.current.loop = true;
          // 默认显示静态视频
          staticVideoRef.current.style.display = 'block';
          await staticVideoRef.current.play().catch(e => {
            console.error('静态视频播放失败:', e);
            document.addEventListener('click', () => {
              staticVideoRef.current?.play().catch(e => console.error('再次尝试播放静态视频失败:', e));
            }, { once: true });
          });
        }

        // 预加载动态视频
        if (dynamicVideoRef.current) {
          // 监听动态视频的加载事件
          dynamicVideoRef.current.addEventListener('loadeddata', () => {
            console.log('[视频] 动态视频数据已加载');
          });

          dynamicVideoRef.current.addEventListener('canplay', () => {
            console.log('[视频] 动态视频可以播放');
            setIsDynamicVideoReady(true);
          });

          // 设置视频属性
          dynamicVideoRef.current.loop = true;
          // 默认隐藏动态视频，但保持在DOM中以便预加载
          dynamicVideoRef.current.style.display = 'none';

          // 开始加载视频
          dynamicVideoRef.current.load();

          // 尝试预播放视频
          try {
            // 设置音量为0，避免任何声音泄漏
            dynamicVideoRef.current.volume = 0;
            // 预播放视频
            await dynamicVideoRef.current.play();
            console.log('[视频] 动态视频开始预播放');

            // 播放一小段后暂停，确保视频已经缓冲
            setTimeout(() => {
              if (dynamicVideoRef.current) {
                // 暂停视频但保持已加载状态
                dynamicVideoRef.current.pause();
                // 重置播放位置到开始
                dynamicVideoRef.current.currentTime = 0;
                console.log('[视频] 动态视频预加载完成');
                setIsDynamicVideoReady(true);
              }
            }, 1000); // 增加预播放时间，确保视频充分缓冲
          } catch (e) {
            console.error('动态视频预播放失败:', e);
            // 即使预播放失败，也标记为准备就绪，后续会在用户交互时尝试播放
            setIsDynamicVideoReady(true);
          }
        }
      } catch (error) {
        console.error('视频初始化失败:', error);
      }
    };

    loadVideos();

    // 添加视频播放结束事件监听
    const handleStaticVideoEnded = () => {
      if (staticVideoRef.current && staticVideoRef.current.style.display === 'block') {
        staticVideoRef.current.play().catch(e => console.error('静态视频循环播放失败:', e));
      }
    };

    const handleDynamicVideoEnded = () => {
      if (dynamicVideoRef.current && dynamicVideoRef.current.style.display === 'block') {
        dynamicVideoRef.current.play().catch(e => console.error('动态视频循环播放失败:', e));
      }
    };

    staticVideoRef.current?.addEventListener('ended', handleStaticVideoEnded);
    dynamicVideoRef.current?.addEventListener('ended', handleDynamicVideoEnded);

    // 添加用户交互事件，确保视频可以播放
    const handleUserInteraction = () => {
      if (dynamicVideoRef.current && dynamicVideoRef.current.paused) {
        dynamicVideoRef.current.play()
          .then(() => {
            dynamicVideoRef.current!.pause();
            dynamicVideoRef.current!.currentTime = 0;
            setIsDynamicVideoReady(true);
            console.log('[视频] 用户交互后动态视频已准备就绪');
          })
          .catch(e => console.error('用户交互后动态视频播放失败:', e));
      }
    };

    document.addEventListener('click', handleUserInteraction, { once: true });

    return () => {
      staticVideoRef.current?.removeEventListener('ended', handleStaticVideoEnded);
      dynamicVideoRef.current?.removeEventListener('ended', handleDynamicVideoEnded);
      document.removeEventListener('click', handleUserInteraction);
    };
  }, []);

  // 根据音频活跃状态切换视频
  useEffect(() => {
    if (!staticVideoRef.current || !dynamicVideoRef.current) return;
    if (!isDynamicVideoReady && isAudioActive) {
      console.log('[视频] 动态视频尚未准备好，等待中...');
      return; // 如果动态视频未准备好，不进行切换
    }

    console.log('音频活跃状态变化，当前状态:', isAudioActive);

    if (isAudioActive) {
      // 有声音时显示动态视频，隐藏静态视频
      staticVideoRef.current.style.display = 'none';
      dynamicVideoRef.current.style.display = 'block';

      // 确保动态视频正在播放
      if (dynamicVideoRef.current.paused) {
        // 重置播放位置，确保从头开始播放
        dynamicVideoRef.current.currentTime = 0;
        dynamicVideoRef.current.play().catch(e => {
          console.error('动态视频播放失败:', e);
          // 如果自动播放失败，尝试在用户下一次交互时播放
          const playOnInteraction = () => {
            dynamicVideoRef.current?.play().catch(e => console.error('交互后动态视频播放失败:', e));
            document.removeEventListener('click', playOnInteraction);
          };
          document.addEventListener('click', playOnInteraction, { once: true });
        });
      }
    } else {
      // 无声音时显示静态视频，隐藏动态视频
      staticVideoRef.current.style.display = 'block';
      dynamicVideoRef.current.style.display = 'none';

      // 确保静态视频正在播放
      if (staticVideoRef.current.paused) {
        staticVideoRef.current.play().catch(e => {
          console.error('静态视频播放失败:', e);
          // 如果自动播放失败，尝试在用户下一次交互时播放
          const playOnInteraction = () => {
            staticVideoRef.current?.play().catch(e => console.error('交互后静态视频播放失败:', e));
            document.removeEventListener('click', playOnInteraction);
          };
          document.addEventListener('click', playOnInteraction, { once: true });
        });
      }
    }
  }, [isAudioActive, isDynamicVideoReady]);

  // 处理音频活跃状态变化
  const handleAudioActiveChange = (active: boolean) => {
    console.log('收到音频活跃状态变化:', active);
    setIsAudioActive(active);
  };

  // 处理开始对话
  const handleStartChat = () => {
    setIsConnecting(true);
    setShowRTC(true);

    // 确保动态视频已准备就绪
    if (dynamicVideoRef.current && !isDynamicVideoReady) {
      dynamicVideoRef.current.play()
        .then(() => {
          dynamicVideoRef.current!.pause();
          dynamicVideoRef.current!.currentTime = 0;
          setIsDynamicVideoReady(true);
          console.log('[视频] 用户点击后动态视频已准备就绪');
        })
        .catch(e => console.error('用户点击后动态视频准备失败:', e));
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-4 bg-gray-100">
      <div className="w-full max-w-[375px] h-[812px] bg-white rounded-[3rem] shadow-2xl overflow-hidden relative">
        {/* 手机顶部刘海 */}
        <div className="absolute top-0 left-1/2 transform -translate-x-1/2 w-[150px] h-[25px] bg-black rounded-b-[1rem] z-10"></div>

        {/* 视频播放器 */}
        <div className="w-full h-full relative">
          {/* 静态视频 - 默认显示 */}
          <video
            ref={staticVideoRef}
            className="w-full h-full object-cover absolute top-0 left-0"
            src="/videos/static.mp4"
            loop
            muted
            playsInline
            preload="auto"
          />

          {/* 动态视频 - 有声音时显示 */}
          <video
            ref={dynamicVideoRef}
            className="w-full h-full object-cover absolute top-0 left-0"
            src="/videos/dynamic.mp4"
            loop
            muted
            playsInline
            preload="auto"
          />

          {/* 配置按钮 */}
          <Link href="/settings" className="absolute top-4 right-4 p-2 bg-white/80 rounded-full shadow-lg hover:bg-white transition-colors z-20">
            <Cog6ToothIcon className="w-6 h-6 text-gray-800" />
          </Link>

          {/* 开始对话按钮 */}
          <div className="absolute bottom-20 left-1/2 transform -translate-x-1/2 z-20">
            <button
              onClick={handleStartChat}
              disabled={isConnecting}
              className={`
                px-8 py-3 rounded-full text-lg font-medium shadow-lg
                transition-all duration-200 transform hover:scale-105
                ${isConnecting ? 'bg-gray-400 cursor-not-allowed' : isConnected ? 'bg-red-500 hover:bg-red-600' : 'bg-blue-500 hover:bg-blue-600'}
                text-white
              `}
            >
              {isConnecting ? '连接中...' : isConnected ? '断开连接' : '开始对话'}
            </button>
          </div>

          {/* RTC 组件 */}
          {showRTC && (
            <RTCComponent
              isConnecting={isConnecting}
              isConnected={isConnected}
              onConnectingChange={setIsConnecting}
              onConnectedChange={setIsConnected}
              onAudioActiveChange={handleAudioActiveChange}
            />
          )}
        </div>

        {/* 手机底部按钮 */}
        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 w-[120px] h-[4px] bg-gray-300 rounded-full"></div>
      </div>
    </main>
  );
} 