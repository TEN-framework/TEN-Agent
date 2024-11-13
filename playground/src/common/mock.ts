import { getRandomUserId } from "./utils";
import { IChatItem, EMessageType } from "@/types";

const SENTENCES = [
  "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
  "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium.",
  "Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit.",
  "Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit.",
  "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
  "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.",
  "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
];

export const genRandomParagraph = (num: number = 0): string => {
  let paragraph = "";
  for (let i = 0; i < num; i++) {
    const randomIndex = Math.floor(Math.random() * SENTENCES.length);
    paragraph += SENTENCES[randomIndex] + " ";
  }

  return paragraph.trim();
};

export const genRandomChatList = (num: number = 10): IChatItem[] => {
  const arr: IChatItem[] = [];
  for (let i = 0; i < num; i++) {
    const type = Math.random() > 0.5 ? EMessageType.AGENT : EMessageType.USER;
    arr.push({
      userId: getRandomUserId(),
      userName: type == "agent" ? EMessageType.AGENT : "You",
      text: genRandomParagraph(3),
      type,
      time: Date.now(),
    });
  }

  return arr;
};
