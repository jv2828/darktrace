import React from 'react';
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
      <Card className="max-w-md w-full text-center space-y-4 p-8">
        <div className="text-4xl font-extrabold font-mono text-slate-500">404</div>
        <div>
          <h1 className="text-lg font-bold text-slate-100">Page Not Found</h1>
          <p className="text-xs text-slate-400 mt-2">
            The requested DARKTRACE intelligence view or resource does not exist.
          </p>
        </div>
        <div className="pt-2">
          <Link to="/dashboard">
            <Button variant="primary" size="sm">
              Return to Dashboard
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}

