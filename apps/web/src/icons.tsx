export function ApplianceIcon({ kind, large = false }: { kind: string; large?: boolean }) {
  return <svg viewBox="0 0 72 76" fill="none" aria-hidden="true" className={large ? 'appliance-icon large' : 'appliance-icon'}>
    {kind === 'fridge' ? <>
      <rect x="19" y="8" width="34" height="58" rx="4" />
      <path d="M19 28h34M27 17v5M27 37v12M25 68h4m14 0h4" />
      <path d="M35 8v20" className="icon-subtle" />
    </> : kind === 'dishwasher' ? <>
      <rect x="12" y="12" width="48" height="52" rx="4" />
      <path d="M12 24h48M22 18h14m13 0h2M21 31h30v22H21zM24 38h24M29 33v18m9-18v18m7-18v18" />
      <path d="M18 68h36" className="icon-subtle" />
    </> : <>
      <rect x="8" y="21" width="56" height="35" rx="4" />
      <rect x="14" y="27" width="35" height="22" rx="2" />
      <path d="M56 29v5m0 6v1m0 5v1M16 59h6m28 0h6M20 36c4-4 7 4 11 0s7 4 11 0m-22 5c4-4 7 4 11 0s7 4 11 0" />
    </>}
  </svg>;
}

export function ArrowIcon({ className = '' }: { className?: string }) {
  return <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function SearchIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" strokeWidth="1.6" /><path d="m16 16 4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>;
}
