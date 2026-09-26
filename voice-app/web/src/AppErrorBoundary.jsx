import { Component } from 'react'

export default class AppErrorBoundary extends Component {
  state = { hasCrashed: false }

  static getDerivedStateFromError() {
    return { hasCrashed: true }
  }

  componentDidCatch(error, info) {
    console.error('The page crashed', error, info)
  }

  reloadPage = () => {
    window.location.reload()
  }

  render() {
    if (!this.state.hasCrashed) return this.props.children
    return (
      <main className="page">
        <div className="card fallback" role="alert">
          <h1>Something went wrong</h1>
          <p className="subtitle">The page hit a problem. Reset to start again.</p>
          <button type="button" className="call-button" onClick={this.reloadPage}>Reset</button>
        </div>
      </main>
    )
  }
}
