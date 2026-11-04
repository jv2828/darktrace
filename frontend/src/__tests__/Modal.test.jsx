import React, { useState } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Modal from '../components/ui/Modal';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';

function ModalParentWithState({ defaultOpen = true, onCloseProp }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [text, setText] = useState('');

  // Parent re-renders on every keystroke with a brand-new inline onClose callback
  return (
    <div>
      <button
        type="button"
        id="trigger-btn"
        onClick={() => setIsOpen(true)}
      >
        Open Modal
      </button>

      <Modal
        isOpen={isOpen}
        onClose={() => {
          if (onCloseProp) onCloseProp();
          setIsOpen(false);
        }}
        title="Investigation Setup"
      >
        <div>
          <Input
            label="Case Title"
            id="case-title"
            value={text}
            onChange={(e) => setText(e.target.value)}
            autoFocus
          />
          <div className="mt-4 flex gap-2">
            <Button
              variant="secondary"
              id="cancel-btn"
              onClick={() => setIsOpen(false)}
            >
              Cancel
            </Button>
            <Button variant="primary" id="save-btn" type="submit">
              Save
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

describe('Modal Component & Focus Stability (Regression Test)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps focus inside input across keystrokes when parent re-renders with new inline onClose', async () => {
    const user = userEvent.setup();
    render(<ModalParentWithState />);

    const input = screen.getByLabelText('Case Title');
    // Initially autoFocused on open
    expect(document.activeElement).toBe(input);

    // Type full word "hello"
    await user.type(input, 'hello');

    // Value should be "hello" without focus jumping to the close button
    expect(input).toHaveValue('hello');
    expect(document.activeElement).toBe(input);
  });

  it('calls onClose when Escape key is pressed', async () => {
    const user = userEvent.setup();
    const handleClose = vi.fn();
    render(<ModalParentWithState onCloseProp={handleClose} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await user.keyboard('{Escape}');

    expect(handleClose).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('traps Tab navigation within modal focusable elements', async () => {
    const user = userEvent.setup();
    render(<ModalParentWithState />);

    const input = screen.getByLabelText('Case Title');
    const closeBtn = screen.getByRole('button', { name: /close dialog/i });
    const cancelBtn = screen.getByRole('button', { name: /cancel/i });
    const saveBtn = screen.getByRole('button', { name: /save/i });

    // Initial focus on input
    expect(document.activeElement).toBe(input);

    // Tab to Cancel button
    await user.tab();
    expect(document.activeElement).toBe(cancelBtn);

    // Tab to Save button
    await user.tab();
    expect(document.activeElement).toBe(saveBtn);

    // Tab wraps to the first focusable in DOM order (close button in header)
    await user.tab();
    expect(document.activeElement).toBe(closeBtn);

    // Tab moves back to input
    await user.tab();
    expect(document.activeElement).toBe(input);

    // Shift+Tab moves backward to close button
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(closeBtn);
  });

  it('restores focus to previous active element when modal closes', async () => {
    const user = userEvent.setup();
    render(<ModalParentWithState defaultOpen={false} />);

    const triggerBtn = screen.getByRole('button', { name: /open modal/i });
    triggerBtn.focus();
    expect(document.activeElement).toBe(triggerBtn);

    // Open modal
    await user.click(triggerBtn);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Close modal via Escape
    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      expect(document.activeElement).toBe(triggerBtn);
    });
  });

  it('allows continuous typing of full sentences in NewInvestigationModal without focus jumping', async () => {
    const user = userEvent.setup();
    const NewInvestigationModal = (await import('../components/investigations/NewInvestigationModal')).default;

    function TestWrapper() {
      const [isOpen, setIsOpen] = useState(true);
      return <NewInvestigationModal isOpen={isOpen} onClose={() => setIsOpen(false)} />;
    }

    render(<TestWrapper />);

    const titleInput = screen.getByLabelText(/investigation title/i);
    expect(document.activeElement).toBe(titleInput);

    const fullSentence = 'Dark web threat intelligence operation Alpha';
    await user.type(titleInput, fullSentence);

    expect(titleInput).toHaveValue(fullSentence);
    expect(document.activeElement).toBe(titleInput);

    const descTextarea = screen.getByPlaceholderText(/add investigation objectives/i);
    await user.click(descTextarea);
    expect(document.activeElement).toBe(descTextarea);

    const descSentence = 'Tracking cybercriminal marketplace syndicates across forums.';
    await user.type(descTextarea, descSentence);

    expect(descTextarea).toHaveValue(descSentence);
    expect(document.activeElement).toBe(descTextarea);
  });

  it('allows continuous typing of full sentences in UsersPage create user modal without focus jumping', async () => {
    const user = userEvent.setup();

    function UsersModalWrapper() {
      const [isOpen, setIsOpen] = useState(true);
      const [fullName, setFullName] = useState('');
      const [username, setUsername] = useState('');
      const [email, setEmail] = useState('');
      const [password, setPassword] = useState('');

      return (
        <Modal
          isOpen={isOpen}
          onClose={() => setIsOpen(false)}
          title="Provision New User"
        >
          <form onSubmit={(e) => e.preventDefault()}>
            <Input
              label="Full Name"
              id="full-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoFocus
            />
            <Input
              label="Username"
              id="user-name"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <Input
              label="Email Address"
              id="user-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label="Initial Password"
              id="user-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </form>
        </Modal>
      );
    }

    render(<UsersModalWrapper />);

    // Full name is autoFocused
    const fullNameInput = screen.getByLabelText('Full Name');
    expect(document.activeElement).toBe(fullNameInput);

    await user.type(fullNameInput, 'Special Agent John Doe');
    expect(fullNameInput).toHaveValue('Special Agent John Doe');
    expect(document.activeElement).toBe(fullNameInput);

    const usernameInput = screen.getByLabelText('Username');
    await user.click(usernameInput);
    await user.type(usernameInput, 'johndoe_cyber');
    expect(usernameInput).toHaveValue('johndoe_cyber');
    expect(document.activeElement).toBe(usernameInput);

    const emailInput = screen.getByLabelText('Email Address');
    await user.click(emailInput);
    await user.type(emailInput, 'johndoe@cyberintel.org');
    expect(emailInput).toHaveValue('johndoe@cyberintel.org');
    expect(document.activeElement).toBe(emailInput);

    const passwordInput = screen.getByLabelText('Initial Password');
    await user.click(passwordInput);
    await user.type(passwordInput, 'Secur3P@ssw0rd123');
    expect(passwordInput).toHaveValue('Secur3P@ssw0rd123');
    expect(document.activeElement).toBe(passwordInput);
  });
});
