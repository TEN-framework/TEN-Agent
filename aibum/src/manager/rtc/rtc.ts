'use client';

import AgoraRTC, {
  IAgoraRTCClient,
  IMicrophoneAudioTrack,
  IRemoteAudioTrack,
  UID,
} from 'agora-rtc-sdk-ng';
import { EMessageDataType, EMessageType, ITextItem } from '@/types';
import { AGEventEmitter } from '../events';
import { RtcEvents, IUserTracks, IRtcUser, IChatItem } from './types';
import { apiGenAgoraData } from '@/common/request';
import { VideoSourceType } from '@/common/constants';

const TIMEOUT_MS = 5000; // 不完整消息的超时时间

interface TextDataChunk {
  message_id: string;
  part_index: number;
  total_parts: number;
  content: string;
}

export class RtcManager extends AGEventEmitter<RtcEvents> {
  private _joined: boolean;
  client: IAgoraRTCClient;
  localTracks: IUserTracks;
  appId: string | null = null;
  token: string | null = null;
  userId: number | null = null;
  private messageCache: { [key: string]: TextDataChunk[] } = {};

  constructor() {
    super();
    this._joined = false;
    this.localTracks = {};
    this.client = AgoraRTC.createClient({ mode: 'rtc', codec: 'vp8' });
    this._listenRtcEvents();
  }

  /**
   * 加入频道
   */
  async join({ channel, userId }: { channel: string; userId: number }) {
    if (!this._joined) {
      const res = await apiGenAgoraData({ channel, userId });
      const { code, data } = res;
      if (code != 0) {
        throw new Error('获取 Agora 令牌失败');
      }
      const { appId, token } = data;
      this.appId = appId;
      this.token = token;
      this.userId = userId;
      await this.client?.join(appId, channel, token, userId);
      this._joined = true;
    }
  }

  /**
   * 创建摄像头视频轨道
   */
  async createCameraTracks() {
    try {
      const videoTrack = await AgoraRTC.createCameraVideoTrack();
      this.localTracks.videoTrack = videoTrack;
    } catch (err) {
      console.error('创建视频轨道失败', err);
    }
    this.emit('localTracksChanged', this.localTracks);
  }

  /**
   * 创建麦克风音频轨道
   */
  async createMicrophoneAudioTrack() {
    try {
      // 使用 Agora SDK 创建音频轨道
      console.log('开始创建 Agora 麦克风音频轨道...');
      const audioTrack = await AgoraRTC.createMicrophoneAudioTrack();

      this.localTracks.audioTrack = audioTrack;
      console.log('创建麦克风音频轨道成功', audioTrack);
    } catch (err: any) {
      console.error('创建麦克风音频轨道失败:', err);
      // 记录更详细的错误信息
      if (err instanceof Error) {
        console.error('错误类型:', err.name);
        console.error('错误消息:', err.message);
        console.error('错误堆栈:', err.stack);
      }

      // 检查是否是 Agora 特定错误
      if (err.code && err.msg) {
        console.error('Agora 错误码:', err.code);
        console.error('Agora 错误消息:', err.msg);
      }
    }

    // 无论成功失败都触发事件，让组件知道状态
    this.emit('localTracksChanged', this.localTracks);
  }

  /**
   * 创建屏幕共享轨道
   */
  async createScreenShareTrack() {
    try {
      const screenTrack = await AgoraRTC.createScreenVideoTrack({
        encoderConfig: {
          width: 1200,
          height: 800,
          frameRate: 5
        }
      }, 'disable');
      this.localTracks.screenTrack = screenTrack;
    } catch (err) {
      console.error('创建屏幕共享轨道失败', err);
    }
    this.emit('localTracksChanged', this.localTracks);
  }

  /**
   * 切换视频源
   */
  async switchVideoSource(type: VideoSourceType) {
    if (type === VideoSourceType.SCREEN) {
      await this.createScreenShareTrack();
      if (this.localTracks.screenTrack) {
        this.client.unpublish(this.localTracks.videoTrack);
        this.localTracks.videoTrack?.close();
        this.localTracks.videoTrack = undefined;
        this.client.publish(this.localTracks.screenTrack);
        this.emit('localTracksChanged', this.localTracks);
      }
    } else if (type === VideoSourceType.CAMERA) {
      await this.createCameraTracks();
      if (this.localTracks.videoTrack) {
        this.client.unpublish(this.localTracks.screenTrack);
        this.localTracks.screenTrack?.close();
        this.localTracks.screenTrack = undefined;
        this.client.publish(this.localTracks.videoTrack);
        this.emit('localTracksChanged', this.localTracks);
      }
    }
  }

  /**
   * 发布本地轨道
   */
  async publish() {
    const tracks = [];
    if (this.localTracks.videoTrack) {
      tracks.push(this.localTracks.videoTrack);
    }
    if (this.localTracks.audioTrack) {
      tracks.push(this.localTracks.audioTrack);
    }
    if (tracks.length) {
      await this.client.publish(tracks);
    }
  }

  /**
   * 销毁连接
   */
  async destroy() {
    this.localTracks?.audioTrack?.close();
    this.localTracks?.videoTrack?.close();
    this.localTracks?.screenTrack?.close();
    if (this._joined) {
      await this.client?.leave();
    }
    this._resetData();
  }

  // -------------- 私有方法 --------------

  /**
   * 监听 RTC 事件
   */
  private _listenRtcEvents() {
    this.client.on('network-quality', (quality) => {
      this.emit('networkQuality', quality);
    });

    this.client.on('user-published', async (user, mediaType) => {
      await this.client.subscribe(user, mediaType);
      if (mediaType === 'audio') {
        this._playAudio(user.audioTrack);
      }
      this.emit('remoteUserChanged', {
        userId: user.uid,
        audioTrack: user.audioTrack,
        videoTrack: user.videoTrack,
      });
    });

    this.client.on('user-unpublished', async (user, mediaType) => {
      await this.client.unsubscribe(user, mediaType);
      this.emit('remoteUserChanged', {
        userId: user.uid,
        audioTrack: user.audioTrack,
        videoTrack: user.videoTrack,
      });
    });

    this.client.on('stream-message', (uid: UID, stream: any) => {
      this._parseData(stream);
    });
  }

  /**
   * 解析数据
   */
  private _parseData(data: any): ITextItem | void {
    let decoder = new TextDecoder('utf-8');
    let decodedMessage = decoder.decode(data);

    console.log('[RTC] 原始数据流', decodedMessage);
    this.handleChunk(decodedMessage);
  }

  /**
   * 处理数据块
   */
  handleChunk(formattedChunk: string) {
    try {
      // 按分隔符 "|" 分割数据块
      const [message_id, partIndexStr, totalPartsStr, content] = formattedChunk.split('|');

      const part_index = parseInt(partIndexStr, 10);
      const total_parts = totalPartsStr === '???' ? -1 : parseInt(totalPartsStr, 10); // -1 表示总部分未知

      // 确保 total_parts 已知后再处理
      if (total_parts === -1) {
        console.warn(`消息 ${message_id} 的总部分未知，等待更多部分。`);
        return;
      }

      const chunkData: TextDataChunk = {
        message_id,
        part_index,
        total_parts,
        content,
      };

      // 检查是否已经有该消息的条目
      if (!this.messageCache[message_id]) {
        this.messageCache[message_id] = [];
        // 设置超时以丢弃不完整的消息
        setTimeout(() => {
          if (this.messageCache[message_id]?.length !== total_parts) {
            console.warn(`不完整的消息 ID ${message_id} 已丢弃`);
            delete this.messageCache[message_id]; // 丢弃不完整的消息
          }
        }, TIMEOUT_MS);
      }

      // 按 message_id 缓存此块
      this.messageCache[message_id].push(chunkData);

      // 如果收到所有部分，重建消息
      if (this.messageCache[message_id].length === total_parts) {
        const completeMessage = this.reconstructMessage(this.messageCache[message_id]);
        const { stream_id, is_final, text, text_ts, data_type } = JSON.parse(atob(completeMessage));
        const isAgent = Number(stream_id) != Number(this.userId);

        let textItem: IChatItem = {
          type: isAgent ? EMessageType.AGENT : EMessageType.USER,
          time: text_ts,
          text: text,
          data_type: EMessageDataType.TEXT,
          userId: stream_id,
          isFinal: is_final,
        };

        if (data_type === 'raw') {
          try {
            let { data, type } = JSON.parse(text);
            if (type === 'image_url') {
              textItem = {
                ...textItem,
                data_type: EMessageDataType.IMAGE,
                text: data.image_url,
              };
            } else if (type === 'reasoning') {
              textItem = {
                ...textItem,
                data_type: EMessageDataType.REASON,
                text: data.text,
              };
            }
          } catch (error) {
            console.error('解析 raw 数据失败:', error);
          }
        }

        if (text.trim().length > 0) {
          this.emit('textChanged', textItem);
        }

        // 清理缓存
        delete this.messageCache[message_id];
      }
    } catch (error) {
      console.error('处理数据块时出错:', error);
    }
  }

  /**
   * 从块重建完整消息
   */
  reconstructMessage(chunks: TextDataChunk[]): string {
    // 按部分索引排序块
    chunks.sort((a, b) => a.part_index - b.part_index);

    // 连接所有块以形成完整消息
    return chunks.map(chunk => chunk.content).join('');
  }

  /**
   * 播放音频
   */
  _playAudio(audioTrack: IMicrophoneAudioTrack | IRemoteAudioTrack | undefined) {
    if (audioTrack && !audioTrack.isPlaying) {
      audioTrack.play();
    }
  }

  /**
   * 重置数据
   */
  private _resetData() {
    this.localTracks = {};
    this._joined = false;
  }
}

// 创建单例
export const rtcManager = new RtcManager(); 