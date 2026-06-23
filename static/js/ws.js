export class QuizSocket {
  constructor(quizId, onMessage, onClose) {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    this.quizId = quizId;
    this.onMessage = onMessage;
    this.onCloseCb = onClose;
    this._queue = [];        // messages sent before the socket opened
    this._closedByUser = false;
    this._connect();
  }

  _connect() {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    this.ws = new WebSocket(`${protocol}://${location.host}/ws/quiz/${this.quizId}`);

    this.ws.onopen = () => {
      // Flush any messages that were queued while connecting
      while (this._queue.length) {
        this.ws.send(JSON.stringify(this._queue.shift()));
      }
    };

    this.ws.onmessage = (e) => {
      try { this.onMessage(JSON.parse(e.data)); } catch {}
    };

    this.ws.onclose = (e) => {
      if (this.onCloseCb) this.onCloseCb(e);
      // Auto-reconnect unless the user closed it deliberately
      if (!this._closedByUser) {
        setTimeout(() => this._connect(), 1500);
      }
    };

    this.ws.onerror = () => {
      try { this.ws.close(); } catch {}
    };
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      // Not open yet — queue it and flush on open
      this._queue.push(data);
    }
  }

  close() {
    this._closedByUser = true;
    this.ws.close();
  }
}
