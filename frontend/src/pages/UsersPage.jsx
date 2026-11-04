import React, { useState, useEffect, useCallback } from 'react';
import PageHeader from '../components/ui/PageHeader';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import Table from '../components/ui/Table';
import Modal from '../components/ui/Modal';
import Input from '../components/ui/Input';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import { fetchUsers, createUserApi, updateUserApi } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ui/Toast';

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const toast = useToast();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Create User Modal state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createEmail, setCreateEmail] = useState('');
  const [createUsername, setCreateUsername] = useState('');
  const [createFullName, setCreateFullName] = useState('');
  const [createRole, setCreateRole] = useState('investigator');
  const [createPassword, setCreatePassword] = useState('');
  const [createError, setCreateError] = useState(null);
  const [createLoading, setCreateLoading] = useState(false);

  // Updating user ID (e.g. toggling active status)
  const [updatingId, setUpdatingId] = useState(null);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchUsers({ page: 1, page_size: 100 });
      setUsers(res.data || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  function resetCreateForm() {
    setCreateEmail('');
    setCreateUsername('');
    setCreateFullName('');
    setCreateRole('investigator');
    setCreatePassword('');
    setCreateError(null);
    setCreateLoading(false);
  }

  async function handleCreateUser(e) {
    e.preventDefault();
    setCreateError(null);

    if (!createEmail.trim() || !createUsername.trim() || !createFullName.trim() || !createPassword) {
      setCreateError('All fields are required.');
      return;
    }

    setCreateLoading(true);

    try {
      const newUser = await createUserApi({
        email: createEmail.trim(),
        username: createUsername.trim(),
        full_name: createFullName.trim(),
        role: createRole,
        password: createPassword,
      });

      toast.success(`User "${newUser.username}" provisioned successfully.`);
      setIsCreateOpen(false);
      resetCreateForm();
      loadUsers();
    } catch (err) {
      setCreateError(err.message || 'Failed to create user account.');
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleToggleActive(user) {
    if (user.id === currentUser?.id) {
      toast.error('You cannot deactivate your own account.');
      return;
    }

    setUpdatingId(user.id);
    const targetStatus = !user.is_active;

    try {
      const updated = await updateUserApi(user.id, { is_active: targetStatus });
      toast.success(
        `User "${updated.username}" ${targetStatus ? 'activated' : 'deactivated'}.`
      );
      setUsers((prev) => prev.map((u) => (u.id === user.id ? updated : u)));
    } catch (err) {
      toast.error(err.message || 'Failed to update user status.');
    } finally {
      setUpdatingId(null);
    }
  }

  const tableHeaders = [
    { label: 'User' },
    { label: 'Username' },
    { label: 'Email' },
    { label: 'Role' },
    { label: 'Status' },
    { label: 'Last Login' },
    { label: 'Actions', className: 'text-right' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="User Administration"
        description="Manage investigator credentials, administrative access, and account status."
        action={
          <Button variant="primary" onClick={() => setIsCreateOpen(true)}>
            + Create User
          </Button>
        }
      />

      {/* Loading State */}
      {loading && (
        <div className="py-20 flex flex-col items-center justify-center gap-3">
          <Spinner size="lg" />
          <p className="text-xs text-slate-400 font-mono">Loading user directory...</p>
        </div>
      )}

      {/* Error State */}
      {!loading && error && (
        <ErrorState
          title="Failed to Load User Directory"
          message={error.message || 'Unable to retrieve accounts from database.'}
          details={error.details}
          onRetry={loadUsers}
        />
      )}

      {/* Users Table */}
      {!loading && !error && (
        <>
          {users.length === 0 ? (
            <EmptyState
              title="No users found"
              message="The user directory appears empty."
              action={
                <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)}>
                  Create User
                </Button>
              }
            />
          ) : (
            <Table headers={tableHeaders}>
              {users.map((u) => {
                const isSelf = u.id === currentUser?.id;
                const isBusy = updatingId === u.id;

                return (
                  <tr key={u.id} className="hover:bg-slate-850/50 transition-colors">
                    <td className="py-3 px-4 font-medium text-slate-100">
                      {u.full_name}
                      {isSelf && (
                        <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                          You
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-300">{u.username}</td>
                    <td className="py-3 px-4 text-slate-400">{u.email}</td>
                    <td className="py-3 px-4">
                      <Badge variant={u.role}>{u.role}</Badge>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant={u.is_active ? 'active' : 'inactive'}>
                        {u.is_active ? 'Active' : 'Disabled'}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'Never'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Button
                        variant={u.is_active ? 'danger' : 'secondary'}
                        size="sm"
                        disabled={isSelf || isBusy}
                        loading={isBusy}
                        onClick={() => handleToggleActive(u)}
                        title={isSelf ? 'Cannot deactivate your own account' : undefined}
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </Table>
          )}
        </>
      )}

      {/* Create User Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => {
          setIsCreateOpen(false);
          resetCreateForm();
        }}
        title="Provision New User"
        description="Create an account for an intelligence analyst or system administrator."
      >
        <form onSubmit={handleCreateUser} className="space-y-4">
          {createError && (
            <div className="p-3 rounded bg-rose-950/60 border border-rose-800 text-rose-200 text-xs">
              {createError}
            </div>
          )}

          <Input
            label="Full Name"
            placeholder="e.g. Dr. Alex Vance"
            value={createFullName}
            onChange={(e) => setCreateFullName(e.target.value)}
            required
            autoFocus
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label="Username"
              placeholder="e.g. avance"
              value={createUsername}
              onChange={(e) => setCreateUsername(e.target.value)}
              required
            />

            <div className="w-full space-y-1.5">
              <label className="block text-xs font-medium text-slate-300">
                Assigned Role <span className="text-rose-400">*</span>
              </label>
              <select
                value={createRole}
                onChange={(e) => setCreateRole(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-950 border border-slate-800 rounded text-slate-100 focus:outline-hidden focus:border-sky-400 cursor-pointer"
              >
                <option value="investigator">Investigator</option>
                <option value="admin">Administrator</option>
              </select>
            </div>
          </div>

          <Input
            label="Email Address"
            type="email"
            placeholder="e.g. avance@darktrace.org"
            value={createEmail}
            onChange={(e) => setCreateEmail(e.target.value)}
            required
          />

          <Input
            label="Initial Password"
            type="password"
            placeholder="••••••••••••"
            value={createPassword}
            onChange={(e) => setCreatePassword(e.target.value)}
            required
            helperText="Minimum 10 characters, at least one letter and one digit. Cannot equal username or email."
          />

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setIsCreateOpen(false);
                resetCreateForm();
              }}
              disabled={createLoading}
            >
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit" loading={createLoading}>
              Create User
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

