import React from 'react';

// Bibliothèque d'icônes maison (trait 1.75, coin arrondi) — cohérente sur toute l'app.
const PATHS = {
  mic: (
    <>
      <rect x="9" y="2.5" width="6" height="11" rx="3" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0" />
      <path d="M12 17.5V21M8.5 21h7" />
    </>
  ),
  stop: <rect x="6.5" y="6.5" width="11" height="11" rx="2" />,
  pause: <><rect x="7" y="5" width="3.4" height="14" rx="1.2" /><rect x="13.6" y="5" width="3.4" height="14" rx="1.2" /></>,
  play: <path d="M8 5.5v13l11-6.5-11-6.5Z" />,
  upload: (
    <>
      <path d="M12 16V4" />
      <path d="m7.5 8.5 4.5-4.5 4.5 4.5" />
      <path d="M5 15.5V18a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 18v-2.5" />
    </>
  ),
  fileText: (
    <>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" />
      <path d="M14 3v5h5M9.5 13h5M9.5 16.5h5M9.5 9.5h2" />
    </>
  ),
  download: (
    <>
      <path d="M12 4v12" />
      <path d="m7.5 11.5 4.5 4.5 4.5-4.5" />
      <path d="M5 19.5h14" />
    </>
  ),
  trash: (
    <>
      <path d="M4.5 7h15" />
      <path d="M9.5 7V5a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 5v2" />
      <path d="M6.5 7 7.3 19a2 2 0 0 0 2 1.9h5.4a2 2 0 0 0 2-1.9l.8-12" />
      <path d="M10 10.5v6M14 10.5v6" />
    </>
  ),
  share: (
    <>
      <circle cx="6" cy="12" r="2.7" />
      <circle cx="18" cy="6" r="2.7" />
      <circle cx="18" cy="18" r="2.7" />
      <path d="m8.4 10.7 7.2-3.4M8.4 13.3l7.2 3.4" />
    </>
  ),
  mail: (
    <>
      <rect x="3.5" y="5.5" width="17" height="13" rx="2.5" />
      <path d="m5 7.5 7 6 7-6" />
    </>
  ),
  webhook: (
    <>
      <path d="M9 7.5a3 3 0 1 1 4.5 2.6L8.8 12.8" />
      <path d="M5.5 16.5A3 3 0 1 0 11 17l.3-4.6" />
      <path d="M16.5 9.5A3 3 0 1 1 18 15l-4.7-.2" />
    </>
  ),
  sparkles: (
    <>
      <path d="M12 4.5 13.4 9l4.6 1.4-4.6 1.4L12 16.3l-1.4-4.5L6 10.4 10.6 9 12 4.5Z" />
      <path d="M18.5 14.5 19 16.5l2 .5-2 .5-.5 2-.5-2-2-.5 2-.5.5-2ZM5.5 4.5 6 6l1.5.5L6 7l-.5 1.5L5 7l-1.5-.5L5 6l.5-1.5Z" />
    </>
  ),
  chat: (
    <path d="M20.5 11.8a7.7 7.7 0 0 1-8.2 7.7 8.6 8.6 0 0 1-3.8-.8L4 20l1.4-4a7.2 7.2 0 0 1-1-4.2 7.7 7.7 0 0 1 8-7.6 7.7 7.7 0 0 1 8.1 7.6Z" />
  ),
  speaker: (
    <>
      <path d="M4 9.5v5h3.5L13 19V5L7.5 9.5H4Z" />
      <path d="M16 9a4 4 0 0 1 0 6M18.5 7a7.2 7.2 0 0 1 0 10" />
    </>
  ),
  dashboard: (
    <>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.8" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.8" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.8" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.8" />
    </>
  ),
  live: (
    <>
      <circle cx="12" cy="12" r="2.2" />
      <path d="M8.2 8.2a5.4 5.4 0 0 0 0 7.6M15.8 8.2a5.4 5.4 0 0 1 0 7.6M5.8 5.8a8.8 8.8 0 0 0 0 12.4M18.2 5.8a8.8 8.8 0 0 1 0 12.4" />
    </>
  ),
  command: (
    <>
      <path d="M9.5 6.5V17a2 2 0 1 1-2-2h10a2 2 0 1 1-2 2V6.5" />
      <path d="M9.5 6.5a2 2 0 1 0-2 2h10a2 2 0 1 0-2-2" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="3.8" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
    </>
  ),
  moon: <path d="M20 14.5A8.2 8.2 0 0 1 9.5 4 8.2 8.2 0 1 0 20 14.5Z" />,
  globe: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.3 2.2 3.5 5.2 3.5 8.5S14.3 18.3 12 20.5C9.7 18.3 8.5 15.3 8.5 12S9.7 5.7 12 3.5Z" />
    </>
  ),
  logout: (
    <>
      <path d="M14 4H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h7" />
      <path d="M17 8.5 20.5 12 17 15.5M20.5 12H10" />
    </>
  ),
  x: <path d="M6 6l12 12M18 6 6 18" />,
  chevronDown: <path d="m6 9 6 6 6-6" />,
  link: (
    <>
      <path d="M10 14a3.5 3.5 0 0 0 5 0l3-3a3.5 3.5 0 1 0-5-5l-1 1" />
      <path d="M14 10a3.5 3.5 0 0 0-5 0l-3 3a3.5 3.5 0 1 0 5 5l1-1" />
    </>
  ),
  copy: (
    <>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
    </>
  ),
  send: <path d="M4 12 20 4l-6 16-3.5-6.5L4 12Z" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8.5" r="3.2" />
      <path d="M3.5 19.5a5.5 5.5 0 0 1 11 0" />
      <path d="M16 5.6a3.2 3.2 0 0 1 0 5.9M17.5 19.5a5.5 5.5 0 0 0-2.6-4.7" />
    </>
  ),
  refresh: <path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4" />,
  folder: <path d="M3.5 6.5A1.5 1.5 0 0 1 5 5h4l2 2.5h8a1.5 1.5 0 0 1 1.5 1.5v8.5a1.5 1.5 0 0 1-1.5 1.5H5a1.5 1.5 0 0 1-1.5-1.5V6.5Z" />,
  lock: (
    <>
      <rect x="5" y="10.5" width="14" height="10" rx="2" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
    </>
  ),
  arrowRight: <path d="M4 12h15M13 6l6 6-6 6" />,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  waveform: <path d="M3 12h2M7 8v8M11 4.5v15M15 8v8M19 10v4M22 12h-1" />,
  cpu: (
    <>
      <rect x="7" y="7" width="10" height="10" rx="1.8" />
      <path d="M10 3v2.5M14 3v2.5M10 18.5V21M14 18.5V21M3 10h2.5M3 14h2.5M18.5 10H21M18.5 14H21" />
    </>
  ),
};

export default function Icon({ name, size = 20, className = '', strokeWidth = 1.75, ...rest }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`icon ${className}`}
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {PATHS[name] || null}
    </svg>
  );
}
