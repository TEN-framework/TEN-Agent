'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import { getOptionsFromLocal, setOptionsToLocal } from '@/common/storage';
import { VALID_USERS, isValidUser, getUserId } from '@/common/constants';

export default function Settings() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const options = getOptionsFromLocal();
    if (options.username) {
      setUsername(options.username);
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedUsername = username.trim();

    if (!trimmedUsername) {
      setError('用户名不能为空');
      return;
    }

    if (!isValidUser(trimmedUsername)) {
      setError('无效的用户名，请使用以下用户名之一：' + Object.keys(VALID_USERS).join(', '));
      return;
    }

    const userId = getUserId(trimmedUsername);
    const options = getOptionsFromLocal();
    setOptionsToLocal({
      ...options,
      username: trimmedUsername,
      userId: userId
    });
    router.back();
  };

  return (
    <main className="min-h-screen bg-gray-100 p-4">
      <div className="mx-auto max-w-md">
        {/* 顶部导航栏 */}
        <div className="mb-6 flex items-center relative">
          <button
            onClick={() => router.back()}
            className="absolute left-0 flex items-center text-gray-600 hover:text-gray-900"
          >
            <ArrowLeftIcon className="h-6 w-6" />
          </button>
          <h1 className="flex-1 text-center text-xl font-semibold">设置</h1>
        </div>

        {/* 设置表单 */}
        <div className="rounded-lg bg-white p-6 shadow-md">
          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label htmlFor="username" className="mb-2 block text-sm font-medium text-gray-700">
                用户名
              </label>
              <input
                type="text"
                id="username"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value);
                  setError(''); // 清除错误信息
                }}
                className="w-full rounded-lg border border-gray-300 p-2 focus:border-blue-500 focus:outline-none"
                placeholder="请输入用户名"
                required
              />
              {error && (
                <p className="mt-1 text-sm text-red-500">
                  {error}
                </p>
              )}
              <p className="mt-1 text-sm text-gray-500">
                请输入有效的用户名，用于语音对话的识别
              </p>
            </div>
            <button
              type="submit"
              className="w-full rounded-lg bg-blue-500 py-2 text-white hover:bg-blue-600"
            >
              保存
            </button>
          </form>
        </div>
      </div>
    </main>
  );
} 