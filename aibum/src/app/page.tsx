'use client';

import { useEffect, useRef, useState } from 'react';
import { Cog6ToothIcon, XMarkIcon } from '@heroicons/react/24/outline';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import AudioVisualizer from '@/components/AudioVisualizer';
import { useMultibandTrackVolume } from '@/common/hooks';
import { IMicrophoneAudioTrack } from 'agora-rtc-sdk-ng';
import { getOptionsFromLocal, setOptionsToLocal } from '@/common/storage';
import { VALID_USERS, isValidUser, getUserId } from '@/common/constants';

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
  const [isDynamicVideoReady, setIsDynamicVideoReady] = useState(false);
  const [remoteAudioTrack, setRemoteAudioTrack] = useState<IMicrophoneAudioTrack | undefined>();
  const { frequencyBands, isActive } = useMultibandTrackVolume(remoteAudioTrack, 12);
  const [showSettings, setShowSettings] = useState(false);
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');

  // 初始化用户设置
  useEffect(() => {
    const options = getOptionsFromLocal();
    if (options.username) {
      setUsername(options.username);
    }
  }, []);

  // 初始化视频
  useEffect(() => {
    // 确保两个视频都加载完成
    const loadVideos = async () => {
      try {
        // 预加载静态视频
        if (staticVideoRef.current) {
          const staticVideo = staticVideoRef.current;
          staticVideo.load();
          staticVideo.loop = true;
          staticVideo.muted = true;
          staticVideo.playsInline = true;
          // 默认显示静态视频
          staticVideo.style.display = 'block';

          // 立即尝试播放静态视频
          const playStaticVideo = async () => {
            try {
              await staticVideo.play();
            } catch (e) {
              console.error('静态视频播放失败:', e);
              // 如果自动播放失败，在下一帧重试
              requestAnimationFrame(playStaticVideo);
            }
          };
          playStaticVideo();
        }

        // 预加载动态视频
        if (dynamicVideoRef.current) {
          const dynamicVideo = dynamicVideoRef.current;
          dynamicVideo.load();
          dynamicVideo.loop = true;
          dynamicVideo.muted = true;
          dynamicVideo.playsInline = true;
          dynamicVideo.volume = 0;
          // 默认隐藏动态视频
          dynamicVideo.style.display = 'none';

          // 监听动态视频的加载事件
          const handleCanPlay = () => {
            console.log('[视频] 动态视频可以播放');
            setIsDynamicVideoReady(true);
            // 预播放一帧然后暂停，确保视频已缓冲
            dynamicVideo.play().then(() => {
              dynamicVideo.pause();
              dynamicVideo.currentTime = 0;
            }).catch(console.error);
            // 移除事件监听器，确保只触发一次
            dynamicVideo.removeEventListener('canplay', handleCanPlay);
          };

          dynamicVideo.addEventListener('canplay', handleCanPlay);
          return () => {
            dynamicVideo.removeEventListener('canplay', handleCanPlay);
          };
        }
      } catch (error) {
        console.error('视频初始化失败:', error);
      }
    };

    loadVideos();
  }, []);

  // 根据音频活跃状态切换视频
  useEffect(() => {
    if (!staticVideoRef.current || !dynamicVideoRef.current || !isDynamicVideoReady) return;

    const staticVideo = staticVideoRef.current;
    const dynamicVideo = dynamicVideoRef.current;

    const playVideo = async (targetVideo: HTMLVideoElement, currentVideo: HTMLVideoElement) => {
      try {
        // 同步播放进度
        targetVideo.currentTime = currentVideo.currentTime;
        // 确保目标视频已暂停
        targetVideo.pause();
        // 设置显示状态
        targetVideo.style.display = 'block';
        currentVideo.style.display = 'none';
        // 开始播放目标视频
        await targetVideo.play().catch(e => {
          console.error('视频播放失败:', e);
          // 如果播放失败，在下一帧重试
          requestAnimationFrame(() => playVideo(targetVideo, currentVideo));
        });
      } catch (e) {
        console.error('视频切换失败:', e);
        requestAnimationFrame(() => playVideo(targetVideo, currentVideo));
      }
    };

    if (isActive) {
      playVideo(dynamicVideo, staticVideo);
    } else {
      playVideo(staticVideo, dynamicVideo);
    }
  }, [isActive, isDynamicVideoReady]);

  // 处理开始对话
  const handleStartChat = () => {
    if (!username) {
      setShowSettings(true);
      return;
    }
    setIsConnecting(true);
    setShowRTC(true);
  };

  // 处理设置提交
  const handleSettingsSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedUsername = username.trim();
    if (!trimmedUsername) {
      setError('用户名不能为空');
      return;
    }
    if (!isValidUser(trimmedUsername)) {
      setError('无效的用户名');
      return;
    }
    const userId = getUserId(trimmedUsername);
    const options = getOptionsFromLocal();
    setOptionsToLocal({
      ...options,
      username: trimmedUsername,
      userId: userId
    });
    setError('');
    setShowSettings(false);
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
          {!isConnected && (
            <button
              onClick={() => setShowSettings(true)}
              className="absolute top-4 right-4 p-2 bg-white/80 rounded-full shadow-lg hover:bg-white transition-colors z-20"
            >
              <Cog6ToothIcon className="w-6 h-6 text-gray-800" />
            </button>
          )}
          {isConnected && (
            <div className="absolute top-4 right-4 p-2 bg-gray-400 rounded-full shadow-lg cursor-not-allowed z-20">
              <Cog6ToothIcon className="w-6 h-6 text-gray-600" />
            </div>
          )}

          {/* 音频可视化器 */}
          {isConnected && (
            <div className="absolute bottom-[150px] left-1/2 transform -translate-x-1/2 z-20 w-full px-4">
              <div className="bg-black/50 backdrop-blur-sm rounded-lg p-4">
                <div className="text-white text-center text-xl font-medium">Euvola</div>
                <div className="h-[80px] flex items-center justify-center mt-2">
                  <AudioVisualizer
                    type="agent"
                    frequencies={frequencyBands}
                    barWidth={6}
                    minBarHeight={6}
                    maxBarHeight={56}
                    borderRadius={2}
                    gap={6}
                  />
                </div>
              </div>
            </div>
          )}

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
              onAudioTrackChange={setRemoteAudioTrack}
            />
          )}
        </div>

        {/* 手机底部按钮 */}
        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 w-[120px] h-[4px] bg-gray-300 rounded-full"></div>

        {/* 设置弹框 */}
        {showSettings && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg w-[90%] max-w-md p-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-semibold">设置</h2>
                <button
                  onClick={() => setShowSettings(false)}
                  className="p-1 hover:bg-gray-100 rounded-full transition-colors"
                >
                  <XMarkIcon className="w-6 h-6" />
                </button>
              </div>
              <form onSubmit={handleSettingsSubmit}>
                <div className="mb-4">
                  <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
                    用户 ID
                  </label>
                  <input
                    type="text"
                    id="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="请输入用户 ID"
                  />
                  {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
                </div>
                <button
                  type="submit"
                  className="w-full bg-blue-500 text-white py-2 rounded-lg hover:bg-blue-600 transition-colors"
                >
                  确定
                </button>
              </form>
            </div>
          </div>
        )}
      </div>
    </main>
  );
} 