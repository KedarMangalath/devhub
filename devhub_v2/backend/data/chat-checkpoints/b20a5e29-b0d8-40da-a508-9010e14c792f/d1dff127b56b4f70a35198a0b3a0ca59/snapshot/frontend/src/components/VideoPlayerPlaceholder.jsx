import React, { useState } from 'react';
import { Video, Mic, MicOff, VideoOff, PhoneOff } from 'lucide-react';

export default function VideoPlayerPlaceholder({ isDoctor = false, onEndCall }) {
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);

  return (
    <div className="relative w-full bg-gray-950 rounded-2xl overflow-hidden aspect-video flex flex-col items-center justify-center shadow-2xl border border-gray-800">
      
      {/* Main Video Area (Remote Participant) */}
      <div className="flex flex-col items-center justify-center space-y-6 z-10">
        <div className="relative">
          <div className="absolute inset-0 bg-blue-500 rounded-full animate-ping opacity-20"></div>
          <div className="w-24 h-24 bg-gray-800 rounded-full flex items-center justify-center relative z-10 border-4 border-gray-700 shadow-lg">
            <Video className="w-10 h-10 text-blue-400" />
          </div>
        </div>
        <div className="text-center space-y-2">
          <h3 className="text-gray-200 text-xl font-semibold tracking-wide">
            {isDoctor ? "Waiting for patient..." : "Waiting for doctor..."}
          </h3>
          <p className="text-gray-500 text-sm">
            The consultation will begin automatically when they join.
          </p>
        </div>
      </div>

      {/* Self View (Local Participant) */}
      <div className="absolute bottom-28 right-8 w-48 aspect-video bg-gray-900 rounded-xl border-2 border-gray-700 overflow-hidden shadow-2xl flex items-center justify-center z-20 transition-all hover:scale-105">
        {isVideoOff ? (
          <div className="text-gray-500 text-sm flex flex-col items-center">
            <VideoOff className="w-6 h-6 mb-2" />
            <span>Camera Off</span>
          </div>
        ) : (
          <div className="relative w-full h-full">
            <img
              src="https://picsum.photos/seed/teleconsult-self/300/200"
              alt="Self view"
              className="w-full h-full object-cover"
            />
            <div className="absolute bottom-2 left-2 bg-black/60 px-2 py-1 rounded text-xs text-white font-medium">
              You
            </div>
            {isMuted && (
              <div className="absolute top-2 right-2 bg-red-500 p-1 rounded-full text-white">
                <MicOff className="w-3 h-3" />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Controls Overlay */}
      <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-black/90 via-black/50 to-transparent flex justify-center items-center space-x-6 z-30">
        <button
          onClick={() => setIsMuted(!isMuted)}
          className={`p-4 rounded-full transition-all duration-200 shadow-lg ${
            isMuted 
              ? 'bg-red-500 hover:bg-red-600 text-white' 
              : 'bg-gray-700 hover:bg-gray-600 text-white'
          }`}
          title={isMuted ? "Unmute" : "Mute"}
        >
          {isMuted ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
        </button>

        <button
          onClick={() => setIsVideoOff(!isVideoOff)}
          className={`p-4 rounded-full transition-all duration-200 shadow-lg ${
            isVideoOff 
              ? 'bg-red-500 hover:bg-red-600 text-white' 
              : 'bg-gray-700 hover:bg-gray-600 text-white'
          }`}
          title={isVideoOff ? "Turn on camera" : "Turn off camera"}
        >
          {isVideoOff ? <VideoOff className="w-6 h-6" /> : <Video className="w-6 h-6" />}
        </button>

        <button
          onClick={onEndCall}
          className="p-4 rounded-full bg-red-600 hover:bg-red-700 text-white transition-all duration-200 shadow-lg hover:scale-110"
          title="End Call"
        >
          <PhoneOff className="w-6 h-6" />
        </button>
      </div>
      
      {/* Network Status Indicator */}
      <div className="absolute top-6 left-6 flex items-center space-x-2 z-20 bg-black/40 px-3 py-1.5 rounded-full backdrop-blur-sm">
        <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
        <span className="text-xs text-gray-300 font-medium">Secure Connection</span>
      </div>
    </div>
  );
}