import React from 'react';

const Action: React.FC = () => {
  return (
    <div className="flex justify-between items-center p-2 bg-gray-800">
      <button className="bg-blue-500 text-white px-4 py-2 rounded">Action 1</button>
      <button className="bg-green-500 text-white px-4 py-2 rounded">Action 2</button>
    </div>
  );
};

export default Action;