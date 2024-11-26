"use client"

import { useAppDispatch, useAppSelector, useMultibandTrackVolume } from "@/common"
import { TrulienceAvatar } from 'trulience-sdk';
import { IMicrophoneAudioTrack } from 'agora-rtc-sdk-ng';
import styles from "./index.module.scss";
import React from 'react';
import { useRef, useState, useEffect } from "react";
import { rtcManager } from "@/manager";
import { ITextItem } from "@/types";
import { FullScreenIcon } from "@/components/icons/fullsccreen";

let trulienceAvatarInstance: JSX.Element | null = null;
const trulienceAvatarRef = React.createRef<TrulienceAvatar>();

interface AvatarProps {
  audioTrack?: IMicrophoneAudioTrack
}

const Avatar = (props: AvatarProps) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  // Get the received audio track from parent component
  const { audioTrack } = props;
  var lastChatTime = 0;
  var dance = 0;
  var bg = 0;
  var music = 0;

  const urlParams = new URLSearchParams(window.location.search);
  const avatarIdFromURL = urlParams.get('avatarId');
  const finalAvatarId = avatarIdFromURL || process.env.NEXT_PUBLIC_avatarId || '';


  // Keep track of the agent connection status.
  const agentConnected = useAppSelector(state => state.global.agentConnected)
  const options = useAppSelector(state => state.global.options)
  const { userId } = options
  const appDispatch = useAppDispatch()

  const animStrings = [
    "<trl-anim immediate='true' type='core' id='BubblePop_Dance' />",
    "<trl-anim immediate='true' type='core' id='OnTheFloor_Dance' />",
    "<trl-anim immediate='true' type='core' id='Routine_07' />",
    "<trl-anim immediate='true' type='core' id='Shuffle_CrossLimbs_F' />"
  ];

  const bgStrings = [
    "<trl-load-environment immediate='true' gltf-model='"+process.env.NEXT_PUBLIC_animationURL+"/assets/environments/GraffitiWarehouse.glb' position='0 0 0' rotation='0 0 0' scale='1 1 1' />",
    "<trl-load-environment immediate='true' gltf-model='"+process.env.NEXT_PUBLIC_animationURL+"/assets/environments/ColorfulSunsetBeach.glb' position='0 0 0' rotation='0 0 0' scale='1 1 1' />",
    "<trl-load-environment immediate='true' gltf-model='"+process.env.NEXT_PUBLIC_animationURL+"/assets/environments/NorthernLightsForest.glb' position='0 0 0' rotation='0 0 0' scale='1 1 1' />",
    "<trl-load-environment immediate='true' gltf-model='"+process.env.NEXT_PUBLIC_animationURL+"/assets/environments/PsychedelicMountains.glb' position='0 0 0' rotation='0 0 0' scale='1 1 1' />"
  ];

  const musicString = [
    "<trl-play-background-audio immediate='true' volume='0.1' audio='"+process.env.NEXT_PUBLIC_animationURL+"/assets/audio/music/LoFiMusic.mp3' />",
    "<trl-play-background-audio immediate='true' volume='0.1' audio='"+process.env.NEXT_PUBLIC_animationURL+"/assets/audio/music/DanceMusic.mp3' />",
    "<trl-play-background-audio immediate='true' volume='0.1' audio='"+process.env.NEXT_PUBLIC_animationURL+"/assets/audio/music/LoFiMusic.mp3' />",
    "<trl-play-background-audio immediate='true' volume='0.1' audio='"+process.env.NEXT_PUBLIC_animationURL+"/assets/audio/music/DanceMusic.mp3' />"
  ];

  function getDance() {
    let ret = animStrings[dance++]
    if (dance > animStrings.length - 1) {
      dance = 0;
    }
    return ret;
  }

  function getMusic() {
    let ret = musicString[music++]
    if (music > musicString.length - 1) {
      music = 0;
    }
    return ret;
  }

  function getBG() {
    let ret = bgStrings[bg++]
    if (bg > bgStrings.length - 1) {
      bg = 0;
    }
    return ret;
  }

  // Forward the received messages to avatar.
  useEffect(() => {
    // Ensure the listener is added only once
    if (trulienceAvatarRef.current) {
      console.log('adding listener', trulienceAvatarRef);
      rtcManager.on("textChanged", (textItem: ITextItem) => {
        if (textItem.isFinal && textItem.dataType == "transcribe" && textItem.time != lastChatTime) {
          const isAgent = Number(textItem.uid) != Number(userId);
          if (isAgent) {
            let trulienceObj = trulienceAvatarRef.current?.getTrulienceObject();
            lastChatTime = textItem.time;
            let ssml = "";
            if (textItem.text.includes('SSML_DANCE')) {
              ssml = getDance();
            } else if (textItem.text.includes('SSML_CONTENT_HIDE')) {
              ssml = "<trl-content position='DefaultCenter' />";
            } else if (textItem.text.includes('SSML_CONTENT_SHOW')) {
              ssml = "<trl-content position='ScreenAngledMediumLeft' screen='https://www.youtube.com/embed/BHACKCNDMW8?autoplay=1' pointer='true' x='10' y='10' w='50' h='50' index='0' />";             
            } else if (textItem.text.includes('SSML_KISS')) {
              ssml = "<trl-anim immediate='true' type='aux' id='kiss' audio='"+process.env.NEXT_PUBLIC_animationURL+"/assets/audio/female/kiss.mp3' />";
            } else if (textItem.text.includes('SSML_BACKGROUND')) {
              ssml = getBG();
            } else if (textItem.text.includes('SSML_MUSIC_STOP')) {
              ssml = "<trl-stop-background-audio immediate='true' />";
            } else if (textItem.text.includes('SSML_MUSIC')) {
              ssml = getMusic();
            } 
            if (ssml.length > 0) {
              console.log("Play ssml " + ssml);
              trulienceObj?.sendMessageToAvatar(ssml);
            }
          }
        }
      });
    }
  }, []);

  useEffect(() => {
    // create media stream if audioTrack changes and agent is connected.
    if (audioTrack && agentConnected && trulienceAvatarRef.current) {
      // Create and set the media stream object.
      const stream = new MediaStream([audioTrack.getMediaStreamTrack()]);
      // Set the media stream to make avatar speak the text.
      trulienceAvatarRef.current?.setMediaStream(null);
      trulienceAvatarRef.current?.setMediaStream(stream);

      console.warn("Created MediaStream = ",trulienceAvatarRef.current, stream, audioTrack);
    }

    if (!agentConnected && trulienceAvatarRef.current) {
      trulienceAvatarRef.current?.getTrulienceObject()?.sendMessageToAvatar("<trl-stop-background-audio immediate='true' />");
    }

    return () => {
      console.log("Cleanup - setting media-stream null", trulienceAvatarRef.current);
      if(trulienceAvatarRef.current) {
        console.warn('xx',trulienceAvatarRef.current,audioTrack,agentConnected);
        trulienceAvatarRef.current?.setMediaStream(null);
      }
        
    };
  }, [audioTrack, agentConnected]);


  // Sample for listening to truilence notifications.
  // Refer https://trulience.com/docs#/client-sdk/sdk?id=trulience-events for a list of all the events fired by Trulience SDK.
  const authSuccessHandler = (resp: string) => {
    console.log("In callback authSuccessHandler resp = ", resp);
  }

  const websocketConnectHandler = (resp: string) => {
    console.log("In callback websocketConnectHandler resp = ", resp);
  }

  const loadProgress = (progressDetails: { [key: string]: any }) => {
    console.log("In callback loadProgress progressDetails = ", progressDetails);
    if (trulienceAvatarRef.current && progressDetails && progressDetails.percent && progressDetails.percent === 1) {
      console.log("In callback loadProgress percent = ", progressDetails.percent);
         console.log("anims loaded in loadProgress");

      trulienceAvatarRef.current?.getTrulienceObject()?.sendMessageToAvatar("<trl-load animations='"+process.env.NEXT_PUBLIC_animationURL+process.env.NEXT_PUBLIC_animationPackDance+"' />");
      trulienceAvatarRef.current?.getTrulienceObject()?.sendMessageToAvatar("<trl-load animations='"+process.env.NEXT_PUBLIC_animationURL+process.env.NEXT_PUBLIC_animationPackYoga+"' />");

    }
  }

  const eventCallbacks = {
    "auth-success": authSuccessHandler,
    "websocket-connect": websocketConnectHandler,
    "load-progress": loadProgress
  }

  // Ensure TrulienceAvatar is only created once
  if (!trulienceAvatarInstance) {
    trulienceAvatarInstance = (
      <TrulienceAvatar
        url={process.env.NEXT_PUBLIC_trulienceSDK}
        ref={trulienceAvatarRef}
        avatarId={finalAvatarId}
        token={process.env.NEXT_PUBLIC_avatarToken}
        eventCallbacks={eventCallbacks}
        width="100%"
        height="100%"
      />
    );
  }

  return (
    <div className={`${styles.avatar} ${isFullscreen ? styles.fullscreenContainer : ""}`}>
      <div
        className={styles.fullScreenIcon}
        onClick={() => setIsFullscreen(!isFullscreen)}
      >
        <FullScreenIcon active={isFullscreen} />
      </div>

      {trulienceAvatarInstance}
    </div>
  )
}
export default Avatar;