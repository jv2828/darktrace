import React from 'react';
import Card from './Card';
import Button from './Button';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an unhandled render error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Card className="p-6 border-rose-900/50 bg-rose-950/20 text-rose-200">
          <h3 className="text-sm font-semibold text-rose-300">
            {this.props.fallbackTitle || 'View Display Error'}
          </h3>
          <p className="text-xs text-rose-200 mt-1">
            {this.state.error?.message || 'An unexpected rendering error occurred in this view.'}
          </p>
          <div className="mt-4">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              Try Again
            </Button>
          </div>
        </Card>
      );
    }
    return this.props.children;
  }
}

