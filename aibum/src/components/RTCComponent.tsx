'use client';

import { useEffect, useState, useRef } from 'react';
import { IMicrophoneAudioTrack, IRemoteAudioTrack } from 'agora-rtc-sdk-ng';
import { apiStartService, apiStopService, apiPing } from '@/common/request';
import { getOptionsFromLocal, setOptionsToLocal } from '@/common/storage';
import { getRandomChannel } from '@/common/utils';
import { rtcManager, IRtcUser, IUserTracks } from '@/manager';
import { IChatItem } from "@/types";

interface RTCComponentProps {
  isConnecting: boolean;
  isConnected: boolean;
  onConnectingChange: (connecting: boolean) => void;
  onConnectedChange: (connected: boolean) => void;
  onAudioTrackChange: (track: IMicrophoneAudioTrack | undefined) => void;
}

export default function RTCComponent({
  isConnecting,
  isConnected,
  onConnectingChange,
  onConnectedChange,
  onAudioTrackChange
}: RTCComponentProps) {
  // 本地状态
  const [audioTrack, setAudioTrack] = useState<IMicrophoneAudioTrack>();
  const [remoteUser, setRemoteUser] = useState<IRtcUser>();
  const [hasInit, setHasInit] = useState(false);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [chatMessages, setChatMessages] = useState<IChatItem[]>([]);

  // 初始化监听器
  useEffect(() => {
    // 监听本地轨道变化
    rtcManager.on('localTracksChanged', onLocalTracksChanged);

    // 监听远程用户变化
    rtcManager.on('remoteUserChanged', onRemoteUserChanged);

    // 监听文本消息变化
    rtcManager.on('textChanged', onTextChanged);

    return () => {
      // 组件卸载时移除监听器
      rtcManager.off('localTracksChanged', onLocalTracksChanged);
      rtcManager.off('remoteUserChanged', onRemoteUserChanged);
      rtcManager.off('textChanged', onTextChanged);

      // 如果已初始化，则销毁连接
      if (hasInit) {
        destroy();
      }

      // 停止ping
      stopPing();

    };
  }, [hasInit]);

  // 本地轨道变化处理函数
  const onLocalTracksChanged = (tracks: IUserTracks) => {
    console.log('本地轨道变化:', tracks);
    const { audioTrack } = tracks;
    if (audioTrack) {
      setAudioTrack(audioTrack);
    }
  };

  // 远程用户变化处理函数
  const onRemoteUserChanged = (user: IRtcUser) => {
    console.log('远程用户变化:', user);
    if (user.audioTrack) {
      user.audioTrack.play();
      onAudioTrackChange?.(user.audioTrack);
    } else {
      onAudioTrackChange?.(undefined);
    }
  };

  // 文本消息变化处理函数
  const onTextChanged = (textItem: IChatItem) => {
    console.log('收到文本消息:', textItem);

    // 只有当消息是完整的时才添加到聊天记录中
    // 注意：rtcManager已经确保了只有完整的消息才会触发textChanged事件
    setChatMessages(prev => [...prev, textItem]);
  };

  /**
   * 开始定时ping服务器
   * @param channel 频道名称
   * @param interval 间隔时间（毫秒），默认3000ms
   */
  const startPing = (channel: string, interval: number = 3000) => {
    // 如果已经有定时器，先停止
    if (pingIntervalRef.current) {
      stopPing();
    }

    // 确保有channel
    if (!channel) {
      console.error('[RTC] 无法启动ping：channel为空');
      return;
    }

    console.log(`[RTC] 开始定时ping服务器，channel: ${channel}, 间隔: ${interval}ms`);

    // 创建新的定时器
    pingIntervalRef.current = setInterval(() => {
      apiPing(channel).then(res => {
        if (res.code !== 0) {
          console.warn(`[RTC] 服务器响应异常: ${JSON.stringify(res)}`);
        }
      }).catch(err => {
        console.error('[RTC] ping请求失败:', err);
      });
    }, interval);
  };

  /**
   * 停止定时ping服务器
   */
  const stopPing = () => {
    if (pingIntervalRef.current) {
      console.log('[RTC] 停止定时ping服务器');
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  };

  // 初始化 RTC
  const init = async () => {
    console.log('[RTC] 初始化');

    try {
      // 获取本地存储的配置
      const options = getOptionsFromLocal();

      // 尝试创建麦克风音频轨道（即使失败也继续）
      try {
        console.log('[RTC] 尝试创建麦克风音频轨道...');
        await rtcManager.createMicrophoneAudioTrack();
      } catch (audioError) {
        console.warn('[RTC] 创建麦克风音频轨道失败，但将继续连接:', audioError);
        // 继续流程，只是没有本地音频
      }

      // 加入频道
      try {
        console.log('[RTC] 尝试加入频道...');
        await rtcManager.join({
          channel: options.channel,
          userId: parseInt(options.userId)
        });
        console.log('[RTC] 加入频道成功');
      } catch (joinError) {
        console.error('[RTC] 加入频道失败:', joinError);
        throw joinError; // 加入频道失败是致命错误，需要抛出
      }

      // 更新本地存储的配置
      setOptionsToLocal({
        ...options,
        appId: rtcManager.appId ?? '',
        token: rtcManager.token ?? ''
      });

      // 尝试发布本地轨道（即使失败也继续）
      try {
        console.log('[RTC] 尝试发布本地轨道...');
        await rtcManager.publish();
        console.log('[RTC] 发布本地轨道成功');
      } catch (publishError) {
        console.warn('[RTC] 发布本地轨道失败，但将继续连接:', publishError);
        // 继续流程，只是没有发布本地音频
      }

      setHasInit(true);
      console.log('[RTC] 初始化成功');
      return true;
    } catch (error) {
      console.error('[RTC] 初始化失败:', error);
      return false;
    }
  };

  // 销毁 RTC
  const destroy = async () => {
    console.log('[RTC] 销毁');
    await rtcManager.destroy();
    setHasInit(false);
    // 清空聊天消息
    setChatMessages([]);
  };

  // 当 isConnecting 变为 true 时自动开始连接
  useEffect(() => {
    let isHandling = false;  // 添加标志位防止重复调用

    const handleConnection = async () => {
      if (isHandling) return;
      isHandling = true;

      if (isConnecting) {
        if (isConnected) {
          await handleDisconnect();
        } else {
          await handleStartChat();
        }
      }

      isHandling = false;
    };

    handleConnection();
  }, [isConnecting]);  // 只监听 isConnecting 的变化

  // 断开连接
  const handleDisconnect = async () => {
    try {
      const options = getOptionsFromLocal();
      if (options.channel) {
        // 停止服务
        await apiStopService(options.channel);

        // 停止ping
        stopPing();
      }

      // 销毁 RTC 连接
      await destroy();

      // 更新状态
      onConnectedChange(false);
    } catch (error) {
      console.error('断开连接失败:', error);
    } finally {
      onConnectingChange(false);
    }
  };

  // 开始对话处理函数
  const handleStartChat = async () => {
    const options = getOptionsFromLocal();
    console.log('当前配置:', options);

    if (!options.userId) {
      console.log('未找到 userId');
      alert('请先设置用户 ID');
      onConnectingChange(false);
      return;
    }

    try {
      // 确保 userId 是一个有效的数字
      const userIdNum = parseInt(options.userId);

      // 先尝试停止之前的服务，确保清理之前的连接
      try {
        if (options.channel) {
          console.log('尝试停止之前的服务:', options.channel);
          await apiStopService(options.channel);

          // 停止之前的ping
          stopPing();

          // 等待一小段时间确保服务完全停止
          await new Promise(resolve => setTimeout(resolve, 500));

          // 如果已初始化，则销毁连接
          if (hasInit) {
            await destroy();
          }
        }
      } catch (stopError) {
        // 忽略停止服务时的错误，继续尝试新连接
        console.warn('停止之前的服务失败，继续尝试新连接:', stopError);
      }

      // 1. 确保有 channel
      if (!options.channel) {
        const newChannel = getRandomChannel();
        options.channel = newChannel;
        setOptionsToLocal({
          ...options,
          channel: newChannel
        });
      }

      // 2. 初始化 RTC
      const initSuccess = await init();
      if (!initSuccess) {
        throw new Error('RTC 初始化失败');
      }

      // 3. 启动服务端 Agent
      const startResponse = await apiStartService({
        channel: options.channel,
        userId: userIdNum,
        graphName: 'voice_assistant_with_memory',
        language: 'zh-CN',
        voiceType: 'female'
      });

      if (startResponse.code != 0) {  // 使用非严格不等
        console.error('启动服务失败:', startResponse);
        throw new Error('启动服务失败');
      }

      // 启动ping
      startPing(options.channel);

      // 4. 更新连接状态
      onConnectedChange(true);
      console.log('连接成功');

    } catch (error) {
      console.error('连接失败:', error);
      if (hasInit) {
        await destroy();
      }
      onConnectedChange(false);
    } finally {
      onConnectingChange(false);
    }
  };

  // 渲染聊天消息（可选，如果需要在组件中显示聊天内容）
  const renderChatMessages = () => {
    // 暂时隐藏对话内容显示
    return null;

    // 原始显示逻辑（已注释）
    /*
    if (chatMessages.length === 0) return null;

    return (
      <div className="absolute top-20 left-4 right-4 bottom-32 overflow-y-auto bg-black/30 rounded-lg p-4">
        {chatMessages.map((msg, index) => (
          <div
            key={index}
            className={`mb-2 p-2 rounded-lg ${msg.type === 'agent' ? 'bg-blue-500/70 ml-8' : 'bg-gray-700/70 mr-8'}`}
          >
            <p className="text-white">{msg.text}</p>
          </div>
        ))}
      </div>
    );
    */
  };

  // 返回组件，包含聊天消息显示
  return renderChatMessages();
} 