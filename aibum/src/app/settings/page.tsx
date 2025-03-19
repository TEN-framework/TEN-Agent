'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import { getOptionsFromLocal, setOptionsToLocal } from '@/common/storage';

export default function Settings() {
  const router = useRouter();
  const [userId, setUserId] = useState('');

  useEffect(() => {
    const options = getOptionsFromLocal();
    if (options.userId) {
      setUserId(options.userId);
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (userId.trim()) {
      const options = getOptionsFromLocal();
      setOptionsToLocal({
        ...options,
        userId: userId.trim()
      });
      router.back();
    }
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
              <label htmlFor="userId" className="mb-2 block text-sm font-medium text-gray-700">
                用户 ID
              </label>
              <input
                type="text"
                id="userId"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                className="w-full rounded-lg border border-gray-300 p-2 focus:border-blue-500 focus:outline-none"
                placeholder="请输入用户 ID"
                required
              />
              <p className="mt-1 text-sm text-gray-500">
                请输入一个唯一的用户 ID，这将用于语音对话的识别
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