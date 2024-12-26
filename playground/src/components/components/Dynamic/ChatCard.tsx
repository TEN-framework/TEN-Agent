"use client";

import React from "react";

const ChatCard: React.FC = () => {
  return (
    <div className="chat-card">
      <h2 className="text-lg font-bold">Chat</h2>
      <div className="chat-messages">
        {/* Chat messages will be rendered here */}
      </div>
      <input
        type="text"
        placeholder="Type a message..."
        className="chat-input"
      />
      <button className="send-button">Send</button>
    </div>
  );
};

export default ChatCard;