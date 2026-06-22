export class QuizSocket {
  constructor(quizId, onMessage, onClose) {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    this.ws = new WebSocket(`${protocol}://${location.host}/ws/quiz/${quizId}`);
    this.ws.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data)); } catch {}
    };
    if (onClose) this.ws.onclose = onClose;
  }

  send(data) {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  close() { this.ws.close(); }
}
