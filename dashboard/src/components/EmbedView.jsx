export default function EmbedView({ url, title }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <div className="section-title" style={{ margin: 0 }}>{title}</div>
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          style={{ fontSize: '0.8rem', color: '#3B82F6', textDecoration: 'none', fontWeight: 500 }}
        >
          Open in new tab ↗
        </a>
      </div>
      <div className="embed-wrap">
        <iframe src={url} title={title} />
      </div>
    </div>
  )
}
