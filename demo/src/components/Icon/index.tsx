import * as React from "react"

import { cn } from "@/lib/utils"

export const GitHubIcon = (props: React.SVGProps<SVGSVGElement>) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="currentColor"
      viewBox="0 0 16 16"
      {...props}
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8" />
    </svg>
  )
}

export const AnimatedSpinnerIcon = (props: React.SVGProps<SVGSVGElement>) => {
  const { className, ...rest } = props
  return (
    <svg
      className={cn("-ml-1 mr-3 h-5 w-5 animate-spin text-white", className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      {...rest}
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      ></circle>
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      ></path>
    </svg>
  )
}

export const LogoIcon = (props: React.SVGProps<SVGSVGElement>) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 98 22"
      fill="none"
      {...props}
    >
      <path
        d="M20.0608 10.2196V1.78906H11.4839C14.5315 10.1796 11.5648 8.12814 20.0608 10.2196Z"
        fill="url(#paint0_linear_8452_794)"
      />
      <path
        d="M10.9207 21.6461H21.6822V11.3105C10.6466 14.2404 15.1169 10.9616 10.9207 21.6461Z"
        fill="url(#paint1_linear_8452_794)"
      />
      <path
        d="M1.62134 11.7246V20.1553H10.1984C7.15085 11.7647 10.1175 13.8162 1.62134 11.7246Z"
        fill="url(#paint2_linear_8452_794)"
      />
      <path
        d="M10.7403 0.353516H0V10.6344C11.0168 7.70963 6.58066 10.9722 10.7403 0.353516Z"
        fill="url(#paint3_linear_8452_794)"
      />
      <path
        d="M30.8442 17.7842H27L30.1964 4.35352H37.2371L40.4307 17.7842H36.5893L35.9841 14.9062H31.4494L30.8442 17.7842ZM33.0462 6.90464L31.86 12.5849H35.5735L34.3846 6.90464H33.0462Z"
        fill="white"
      />
      <path
        d="M42.0108 17.7842H51.3611L53.8614 15.5576V10.1096L45.6285 9.47707V7.15573H53.8614V4.35352H44.5086L42.0108 6.58013V11.8363L50.2411 12.4688V14.9821H42.0108V17.7842Z"
        fill="white"
      />
      <path
        d="M59.4509 17.7842H63.2801V7.03966H67.2922V4.35352H55.4415V7.03966H59.4509V17.7842Z"
        fill="white"
      />
      <path
        d="M78.734 4.35352L81.4548 6.69383V11.6255L79.7584 13.1036L82.303 17.7842H78.1088L76.2555 13.9848H72.6204V17.7842H68.8723V4.35352H78.734ZM72.6204 6.92359V11.4147H77.7068V6.92359H72.6204Z"
        fill="white"
      />
      <path
        d="M87.7273 17.7842H83.8831L87.0795 4.35352H94.1174L97.3138 17.7842H93.4696L92.8645 14.9062H88.3298L87.7273 17.7842ZM89.9293 6.90464L88.7403 12.5849H92.4539L91.2676 6.90464H89.9293Z"
        fill="white"
      />
      <defs>
        <linearGradient
          id="paint0_linear_8452_794"
          x1="11.4569"
          y1="1.76871"
          x2="20.0726"
          y2="9.77396"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#44BBFE" />
          <stop offset="1" stopColor="#4D80FF" />
        </linearGradient>
        <linearGradient
          id="paint1_linear_8452_794"
          x1="21.9247"
          y1="10.9999"
          x2="10.8474"
          y2="21.4681"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#4E7AFF" />
          <stop offset="1" stopColor="#5930FF" />
        </linearGradient>
        <linearGradient
          id="paint2_linear_8452_794"
          x1="0.988861"
          y1="11.6147"
          x2="10.22"
          y2="20.2357"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#33D7B3" />
          <stop offset="1" stopColor="#23EE6E" />
        </linearGradient>
        <linearGradient
          id="paint3_linear_8452_794"
          x1="10.8411"
          y1="0.538082"
          x2="-0.236248"
          y2="11.0064"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#43BEFB" />
          <stop offset="1" stopColor="#34D4BA" />
        </linearGradient>
      </defs>
    </svg>
  )
}

export const SmallLogoIcon = (props: React.SVGProps<SVGSVGElement>) => {
  return (
    <svg
      viewBox="0 0 22 22"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        d="M20.3746 9.86607V1.43555H11.7977C14.8452 9.82607 11.8786 7.77462 20.3746 9.86607Z"
        fill="url(#paint0_linear_8450_1751)"
      />
      <path
        d="M11.2344 21.2925H21.996V10.957C10.9604 13.8869 15.4307 10.6081 11.2344 21.2925Z"
        fill="url(#paint1_linear_8450_1751)"
      />
      <path
        d="M1.93512 11.3711V19.8017H10.5122C7.46464 11.4112 10.4312 13.4627 1.93512 11.3711Z"
        fill="url(#paint2_linear_8450_1751)"
      />
      <path
        d="M11.0541 0H0.313782V10.2809C11.3306 7.35611 6.89444 10.6187 11.0541 0Z"
        fill="url(#paint3_linear_8450_1751)"
      />
      <defs>
        <linearGradient
          id="paint0_linear_8450_1751"
          x1="11.7707"
          y1="1.41519"
          x2="20.3864"
          y2="9.42044"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#44BBFE" />
          <stop offset="1" stopColor="#4D80FF" />
        </linearGradient>
        <linearGradient
          id="paint1_linear_8450_1751"
          x1="22.2385"
          y1="10.6464"
          x2="11.1612"
          y2="21.1146"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#4E7AFF" />
          <stop offset="1" stopColor="#5930FF" />
        </linearGradient>
        <linearGradient
          id="paint2_linear_8450_1751"
          x1="1.30264"
          y1="11.2612"
          x2="10.5338"
          y2="19.8822"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#33D7B3" />
          <stop offset="1" stopColor="#23EE6E" />
        </linearGradient>
        <linearGradient
          id="paint3_linear_8450_1751"
          x1="11.1548"
          y1="0.184566"
          x2="0.0775336"
          y2="10.6529"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#43BEFB" />
          <stop offset="1" stopColor="#34D4BA" />
        </linearGradient>
      </defs>
    </svg>
  )
}

export const InfoIcon = (props: React.SVGProps<SVGSVGElement>) => {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M6.33331 2.5C4.67646 2.5 3.33331 3.84315 3.33331 5.5V14.5C3.33331 16.1569 4.67646 17.5 6.33331 17.5H13.6666C15.3235 17.5 16.6666 16.1569 16.6666 14.5V5.5C16.6666 3.84315 15.3235 2.5 13.6666 2.5H6.33331ZM6.66665 5.83333C6.20641 5.83333 5.83331 6.20643 5.83331 6.66667C5.83331 7.1269 6.20641 7.5 6.66665 7.5H9.99998C10.4602 7.5 10.8333 7.1269 10.8333 6.66667C10.8333 6.20643 10.4602 5.83333 9.99998 5.83333H6.66665ZM6.66665 9.16667C6.20641 9.16667 5.83331 9.53976 5.83331 10C5.83331 10.4602 6.20641 10.8333 6.66665 10.8333H13.3333C13.7936 10.8333 14.1666 10.4602 14.1666 10C14.1666 9.53976 13.7936 9.16667 13.3333 9.16667H6.66665ZM6.66665 12.5C6.20641 12.5 5.83331 12.8731 5.83331 13.3333C5.83331 13.7936 6.20641 14.1667 6.66665 14.1667H13.3333C13.7936 14.1667 14.1666 13.7936 14.1666 13.3333C14.1666 12.8731 13.7936 12.5 13.3333 12.5H6.66665Z"
        fill="currentColor"
      />
    </svg>
  )
}

export const PaletteIcon = (props: React.SVGProps<SVGSVGElement>) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <circle cx="13.5" cy="6.5" r=".5" fill="currentColor" />
      <circle cx="17.5" cy="10.5" r=".5" fill="currentColor" />
      <circle cx="8.5" cy="7.5" r=".5" fill="currentColor" />
      <circle cx="6.5" cy="12.5" r=".5" fill="currentColor" />
      <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z" />
    </svg>
  )
}

export const NetworkAverageIcon = (props: React.SVGProps<SVGSVGElement>) => {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M9.49875 10.8689C10.1539 10.8689 10.685 11.3753 10.685 12V19.8689C10.685 20.4936 10.1539 21 9.49875 21C8.8436 21 8.3125 20.4936 8.3125 19.8689V12C8.3125 11.3753 8.8436 10.8689 9.49875 10.8689Z"
        fill="#FFAB08"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M4.18625 14.8033C4.84139 14.8033 5.37249 15.3097 5.37249 15.9344V19.8689C5.37249 20.4936 4.84139 21 4.18625 21C3.5311 21 3 20.4936 3 19.8689V15.9344C3 15.3097 3.5311 14.8033 4.18625 14.8033Z"
        fill="#FFAB08"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M14.656 7.91803C15.3111 7.91803 15.8422 8.42446 15.8422 9.04918V19.8688C15.8422 20.4936 15.3111 21 14.656 21C14.0008 21 13.4697 20.4936 13.4697 19.8688V9.04918C13.4697 8.42446 14.0008 7.91803 14.656 7.91803Z"
        fill="#D0D5DD"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M19.8137 3C20.4688 3 20.9999 3.50643 20.9999 4.13115V19.8689C20.9999 20.4936 20.4688 21 19.8137 21C19.1585 21 18.6274 20.4936 18.6274 19.8689V4.13115C18.6274 3.50643 19.1585 3 19.8137 3Z"
        fill="#D0D5DD"
      />
    </svg>
  )
}

export const NetworkDisconnectedIcon = (
  props: React.SVGProps<SVGSVGElement>,
) => {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M21 4.13115C21 3.50643 20.4689 3 19.8138 3C19.1586 3 18.6275 3.50643 18.6275 4.13115V19.8689C18.6275 20.4936 19.1586 21 19.8138 21C20.4689 21 21 20.4936 21 19.8689V4.13115ZM14.6562 7.91803C15.3113 7.91803 15.8424 8.42447 15.8424 9.04918V19.8689C15.8424 20.4936 15.3113 21 14.6562 21C14.001 21 13.4699 20.4936 13.4699 19.8689V9.04918C13.4699 8.42447 14.001 7.91803 14.6562 7.91803ZM10.6848 12C10.6848 11.3753 10.1537 10.8689 9.49856 10.8689C8.84342 10.8689 8.31232 11.3753 8.31232 12V19.8689C8.31232 20.4936 8.84342 21 9.49856 21C10.1537 21 10.6848 20.4936 10.6848 19.8689V12ZM5.37249 15.9344C5.37249 15.3097 4.84139 14.8033 4.18625 14.8033C3.5311 14.8033 3 15.3097 3 15.9344V19.8689C3 20.4936 3.5311 21 4.18625 21C4.84139 21 5.37249 20.4936 5.37249 19.8689V15.9344Z"
        fill="#D0D5DD"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M13.2441 12.2441C13.5695 11.9186 14.0972 11.9186 14.4226 12.2441L18 15.8215L21.5774 12.2441C21.9028 11.9186 22.4305 11.9186 22.7559 12.2441C23.0814 12.5695 23.0814 13.0972 22.7559 13.4226L19.1785 17L22.7559 20.5774C23.0814 20.9028 23.0814 21.4305 22.7559 21.7559C22.4305 22.0814 21.9028 22.0814 21.5774 21.7559L18 18.1785L14.4226 21.7559C14.0972 22.0814 13.5695 22.0814 13.2441 21.7559C12.9186 21.4305 12.9186 20.9028 13.2441 20.5774L16.8215 17L13.2441 13.4226C12.9186 13.0972 12.9186 12.5695 13.2441 12.2441Z"
        fill="#DF1642"
      />
    </svg>
  )
}

export const NetworkExcellentIcon = (props: React.SVGProps<SVGSVGElement>) => {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M21 4.13115C21 3.50643 20.4689 3 19.8138 3C19.1586 3 18.6275 3.50643 18.6275 4.13115V19.8689C18.6275 20.4936 19.1586 21 19.8138 21C20.4689 21 21 20.4936 21 19.8689V4.13115ZM14.6562 7.91803C15.3113 7.91803 15.8424 8.42447 15.8424 9.04918V19.8689C15.8424 20.4936 15.3113 21 14.6562 21C14.001 21 13.4699 20.4936 13.4699 19.8689V9.04918C13.4699 8.42447 14.001 7.91803 14.6562 7.91803ZM10.6848 12C10.6848 11.3753 10.1537 10.8689 9.49856 10.8689C8.84342 10.8689 8.31232 11.3753 8.31232 12V19.8689C8.31232 20.4936 8.84342 21 9.49856 21C10.1537 21 10.6848 20.4936 10.6848 19.8689V12ZM5.37249 15.9344C5.37249 15.3097 4.84139 14.8033 4.18625 14.8033C3.5311 14.8033 3 15.3097 3 15.9344V19.8689C3 20.4936 3.5311 21 4.18625 21C4.84139 21 5.37249 20.4936 5.37249 19.8689V15.9344Z"
        fill="#18A957"
      />
    </svg>
  )
}

export const NetworkGoodIcon = (props: React.SVGProps<SVGSVGElement>) => {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M9.49875 10.8689C10.1539 10.8689 10.685 11.3753 10.685 12V19.8689C10.685 20.4936 10.1539 21 9.49875 21C8.8436 21 8.3125 20.4936 8.3125 19.8689V12C8.3125 11.3753 8.8436 10.8689 9.49875 10.8689Z"
        fill="#18A957"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M4.18625 14.8033C4.84139 14.8033 5.37249 15.3097 5.37249 15.9344V19.8689C5.37249 20.4936 4.84139 21 4.18625 21C3.5311 21 3 20.4936 3 19.8689V15.9344C3 15.3097 3.5311 14.8033 4.18625 14.8033Z"
        fill="#18A957"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M14.656 7.91803C15.3111 7.91803 15.8422 8.42446 15.8422 9.04918V19.8688C15.8422 20.4936 15.3111 21 14.656 21C14.0008 21 13.4697 20.4936 13.4697 19.8688V9.04918C13.4697 8.42446 14.0008 7.91803 14.656 7.91803Z"
        fill="#18A957"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M19.8137 3C20.4688 3 20.9999 3.50643 20.9999 4.13115V19.8689C20.9999 20.4936 20.4688 21 19.8137 21C19.1585 21 18.6274 20.4936 18.6274 19.8689V4.13115C18.6274 3.50643 19.1585 3 19.8137 3Z"
        fill="#D0D5DD"
      />
    </svg>
  )
}

export const NetworkPoorIcon = (props: React.SVGProps<SVGSVGElement>) => {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M9.49875 10.8689C10.1539 10.8689 10.685 11.3753 10.685 12V19.8689C10.685 20.4936 10.1539 21 9.49875 21C8.8436 21 8.3125 20.4936 8.3125 19.8689V12C8.3125 11.3753 8.8436 10.8689 9.49875 10.8689Z"
        fill="#D0D5DD"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M4.18625 14.8033C4.84139 14.8033 5.37249 15.3097 5.37249 15.9344V19.8689C5.37249 20.4936 4.84139 21 4.18625 21C3.5311 21 3 20.4936 3 19.8689V15.9344C3 15.3097 3.5311 14.8033 4.18625 14.8033Z"
        fill="#DF1642"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M14.656 7.91803C15.3111 7.91803 15.8422 8.42446 15.8422 9.04918V19.8688C15.8422 20.4936 15.3111 21 14.656 21C14.0008 21 13.4697 20.4936 13.4697 19.8688V9.04918C13.4697 8.42446 14.0008 7.91803 14.656 7.91803Z"
        fill="#D0D5DD"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M19.8137 3C20.4688 3 20.9999 3.50643 20.9999 4.13115V19.8689C20.9999 20.4936 20.4688 21 19.8137 21C19.1585 21 18.6274 20.4936 18.6274 19.8689V4.13115C18.6274 3.50643 19.1585 3 19.8137 3Z"
        fill="#D0D5DD"
      />
    </svg>
  )
}

export const NetworkIconByLevel = (
  props: React.SVGProps<SVGSVGElement> & { level?: number },
) => {
  const { level, ...rest } = props
  switch (level) {
    case 0:
      return <NetworkDisconnectedIcon {...rest} />
    case 1:
      return <NetworkExcellentIcon {...rest} />
    case 2:
      return <NetworkGoodIcon {...rest} />
    case 3:
    case 4:
      return <NetworkAverageIcon {...rest} />
    case 5:
      return <NetworkPoorIcon {...rest} />
    case 6:
    default:
      return <NetworkDisconnectedIcon {...rest} />
  }
}
