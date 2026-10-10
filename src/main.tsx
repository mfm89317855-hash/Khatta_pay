import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import './index.css';

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

class RootErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("KhataTalk Caught Runtime Error:", error, errorInfo);
  }

  handleReset = () => {
    try {
      localStorage.removeItem('khattapay_customers');
      localStorage.removeItem('khattapay_transactions');
    } catch (_) {}
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px', backgroundColor: '#f8fafc', fontFamily: 'sans-serif', color: '#0f172a' }}>
          <div style={{ maxWidth: '480px', width: '100%', background: '#ffffff', borderRadius: '16px', padding: '24px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', border: '1px solid #e2e8f0', textAlign: 'center' }}>
            <div style={{ fontSize: '36px', marginBottom: '12px' }}>📗</div>
            <h1 style={{ fontSize: '20px', fontWeight: 'bold', color: '#065f46', marginBottom: '8px' }}>KhataTalk — Voice-First AI Ledger</h1>
            <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '20px' }}>
              App refresh darkaar hai. Neeche diye gaye button par click karein taake latest version load ho sake.
            </p>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'center' }}>
              <button
                onClick={this.handleReset}
                style={{ padding: '10px 18px', background: '#059669', color: '#ffffff', border: 'none', borderRadius: '10px', fontSize: '13px', fontWeight: '600', cursor: 'pointer' }}
              >
                Clear Cache & Reload (ری لوڈ کریں)
              </button>
            </div>
            {this.state.error && (
              <pre style={{ marginTop: '16px', padding: '8px', background: '#f1f5f9', borderRadius: '8px', fontSize: '10px', color: '#dc2626', textAlign: 'left', overflowX: 'auto' }}>
                {this.state.error.message}
              </pre>
            )}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')!).render(
  <RootErrorBoundary>
    <App />
  </RootErrorBoundary>
);
