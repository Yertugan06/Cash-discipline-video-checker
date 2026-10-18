export type IconName =
  | 'alert'
  | 'arrowDown'
  | 'arrowUp'
  | 'arrowUpRight'
  | 'book'
  | 'check'
  | 'circle'
  | 'clock'
  | 'globe'
  | 'info'
  | 'key'
  | 'link'
  | 'loader'
  | 'lock'
  | 'moon'
  | 'play'
  | 'refresh'
  | 'scan'
  | 'shield'
  | 'sun'
  | 'upload'
  | 'video';

export default function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.75,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  };

  switch (name) {
    case 'alert': return <svg {...common}><path d="M10.3 3.8 2.4 17.5A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.7-2.5L13.7 3.8a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>;
    case 'arrowDown': return <svg {...common}><path d="M12 5v14M18 13l-6 6-6-6"/></svg>;
    case 'arrowUp': return <svg {...common}><path d="m18 15-6-6-6 6"/></svg>;
    case 'arrowUpRight': return <svg {...common}><path d="M7 17 17 7M7 7h10v10"/></svg>;
    case 'book': return <svg {...common}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/><path d="M8 7h8M8 11h6"/></svg>;
    case 'check': return <svg {...common}><path d="m5 12 4 4L19 6"/></svg>;
    case 'circle': return <svg {...common}><circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/></svg>;
    case 'clock': return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>;
    case 'globe': return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>;
    case 'info': return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>;
    case 'key': return <svg {...common}><circle cx="8" cy="15" r="4"/><path d="m11 12 8-8M15 8l2 2M17 6l2 2"/></svg>;
    case 'link': return <svg {...common}><path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.2 1.2"/><path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.2-1.2"/></svg>;
    case 'loader': return <svg {...common} className="spinner"><path d="M21 12a9 9 0 1 1-6.2-8.6"/></svg>;
    case 'lock': return <svg {...common}><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/></svg>;
    case 'moon': return <svg {...common}><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.7 8.7 0 1 0 20.5 14.2Z"/></svg>;
    case 'play': return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="m10 8 6 4-6 4Z"/></svg>;
    case 'refresh': return <svg {...common}><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 8A7 7 0 0 1 18 6l2 6M18 16a7 7 0 0 1-11.9 2L4 12"/></svg>;
    case 'scan': return <svg {...common}><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><circle cx="12" cy="12" r="3"/><path d="M2 12h20"/></svg>;
    case 'shield': return <svg {...common}><path d="M12 22s8-3.5 8-10V5l-8-3-8 3v7c0 6.5 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></svg>;
    case 'sun': return <svg {...common}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>;
    case 'upload': return <svg {...common}><path d="M12 16V4M7 9l5-5 5 5"/><path d="M5 14v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"/></svg>;
    case 'video': return <svg {...common}><rect x="3" y="6" width="14" height="12" rx="2"/><path d="m17 10 4-2v8l-4-2"/></svg>;
  }
}
