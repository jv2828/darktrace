import React, { useState } from 'react';
import Modal from '../ui/Modal';
import Input from '../ui/Input';
import Button from '../ui/Button';
import { createInvestigationApi } from '../../lib/api';

export default function NewInvestigationModal({ isOpen, onClose, onSuccess }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function resetForm() {
    setTitle('');
    setDescription('');
    setError(null);
    setSubmitting(false);
  }

  function handleClose() {
    resetForm();
    onClose();
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmedTitle = title.trim();

    if (!trimmedTitle) {
      setError('Investigation title is required.');
      return;
    }

    if (trimmedTitle.length < 3) {
      setError('Title must be at least 3 characters long.');
      return;
    }

    if (trimmedTitle.length > 200) {
      setError('Title cannot exceed 200 characters.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const created = await createInvestigationApi({
        title: trimmedTitle,
        description: description.trim() || undefined,
      });
      resetForm();
      if (onSuccess) {
        onSuccess(created);
      }
    } catch (err) {
      setError(err.message || 'Failed to create investigation.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Start New Investigation"
      description="Create an isolated case workspace to analyze dark web actor activity."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 rounded bg-rose-950/60 border border-rose-800 text-rose-200 text-xs">
            {error}
          </div>
        )}

        <Input
          label="Investigation Title"
          placeholder="e.g. Operation Hydragate"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          autoFocus
          helperText="Between 3 and 200 characters."
        />

        <div className="w-full space-y-1.5">
          <label className="block text-xs font-medium text-slate-300">
            Case Description (Optional)
          </label>
          <textarea
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Add investigation objectives, initial intelligence leads, or case context..."
            className="w-full px-3 py-2 text-sm bg-slate-950 border border-slate-800 rounded text-slate-100 placeholder:text-slate-500 focus:outline-hidden focus:border-sky-400"
          />
          <p className="text-xs text-slate-400">Maximum 2,000 characters.</p>
        </div>

        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
          <Button variant="ghost" size="sm" onClick={handleClose} disabled={submitting}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" type="submit" loading={submitting}>
            Create Investigation
          </Button>
        </div>
      </form>
    </Modal>
  );
}

