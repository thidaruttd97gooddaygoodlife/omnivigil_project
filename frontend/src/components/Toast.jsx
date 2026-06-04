export default function Toast({ toast, onDone }) {
  return (
    <div className="toast" onAnimationEnd={onDone}>
      <div className="toast-title">{toast.title}</div>
      <div className="toast-message">{toast.message}</div>
      <div className="toast-time">{toast.time}</div>
    </div>
  );
}
