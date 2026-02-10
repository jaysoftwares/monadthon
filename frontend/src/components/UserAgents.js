import React, { useState, useEffect, useCallback } from 'react';
import { useWallet } from '../context/WalletContext';
import { Bot, Play, Pause, Trash2, Plus, Settings, TrendingUp, TrendingDown, Activity } from 'lucide-react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * UserAgents - Component for creating and managing automated playing agents
 *
 * Features:
 * - Create agents with different strategies
 * - Configure entry fee ranges and game preferences
 * - Start/stop agents
 * - View agent performance stats
 */
const UserAgents = () => {
  const { address, isConnected } = useWallet();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [error, setError] = useState(null);

  // New agent form state
  const [newAgent, setNewAgent] = useState({
    name: '',
    strategy: 'balanced',
    max_entry_fee_wei: '100000000000000000', // 0.1 MON
    min_entry_fee_wei: '1000000000000000',   // 0.001 MON
    preferred_games: [],
    auto_join: true,
    daily_budget_wei: '0',
  });

  // Fetch agents
  const fetchAgents = useCallback(async () => {
    if (!address) return;

    try {
      const response = await fetch(
        `${API_BASE}/api/agents?owner_address=${address}`
      );
      if (response.ok) {
        const data = await response.json();
        setAgents(data);
      }
    } catch (err) {
      console.error('Error fetching agents:', err);
    } finally {
      setLoading(false);
    }
  }, [address]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  // Create agent
  const createAgent = async () => {
    if (!address || !newAgent.name) return;

    try {
      const response = await fetch(
        `${API_BASE}/api/agents/create?owner_address=${address}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newAgent),
        }
      );

      if (response.ok) {
        const agent = await response.json();
        setAgents([...agents, agent]);
        setShowCreateModal(false);
        setNewAgent({
          name: '',
          strategy: 'balanced',
          max_entry_fee_wei: '100000000000000000',
          min_entry_fee_wei: '1000000000000000',
          preferred_games: [],
          auto_join: true,
          daily_budget_wei: '0',
        });
      } else {
        const err = await response.json();
        setError(err.detail || 'Failed to create agent');
      }
    } catch (err) {
      setError('Failed to create agent');
    }
  };

  // Start/stop agent
  const toggleAgent = async (agentId, currentStatus) => {
    const action = currentStatus === 'active' ? 'stop' : 'start';

    try {
      const response = await fetch(
        `${API_BASE}/api/agents/${agentId}/${action}?owner_address=${address}`,
        { method: 'POST' }
      );

      if (response.ok) {
        fetchAgents();
      }
    } catch (err) {
      console.error(`Error ${action}ing agent:`, err);
    }
  };

  // Delete agent
  const deleteAgent = async (agentId) => {
    if (!window.confirm('Are you sure you want to delete this agent?')) return;

    try {
      const response = await fetch(
        `${API_BASE}/api/agents/${agentId}?owner_address=${address}`,
        { method: 'DELETE' }
      );

      if (response.ok) {
        setAgents(agents.filter(a => a.agent_id !== agentId));
      }
    } catch (err) {
      console.error('Error deleting agent:', err);
    }
  };

  // Format wei to MON
  const formatMON = (wei) => {
    return (BigInt(wei) / BigInt(10 ** 18)).toString() +
           '.' +
           (BigInt(wei) % BigInt(10 ** 18)).toString().padStart(18, '0').slice(0, 4);
  };

  if (!isConnected) {
    return (
      <div className="bg-gray-50 rounded-xl p-8 text-center">
        <Bot className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Connect Wallet</h3>
        <p className="text-gray-600">Connect your wallet to create and manage agents</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Your Agents</h2>
          <p className="text-gray-600">Automated bots that play tournaments for you</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Create Agent
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
          <button onClick={() => setError(null)} className="float-right">&times;</button>
        </div>
      )}

      {/* Agents list */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin w-8 h-8 border-2 border-purple-600 border-t-transparent rounded-full mx-auto" />
        </div>
      ) : agents.length === 0 ? (
        <div className="bg-gray-50 rounded-xl p-12 text-center">
          <Bot className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-900 mb-2">No Agents Yet</h3>
          <p className="text-gray-600 mb-6">
            Create your first agent to start earning passively
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            Create Your First Agent
          </button>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {agents.map((agent) => (
            <div
              key={agent.agent_id}
              className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-md transition-shadow"
            >
              {/* Agent header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    agent.status === 'active' ? 'bg-green-100' :
                    agent.status === 'in_game' ? 'bg-blue-100' :
                    'bg-gray-100'
                  }`}>
                    <Bot className={`w-5 h-5 ${
                      agent.status === 'active' ? 'text-green-600' :
                      agent.status === 'in_game' ? 'text-blue-600' :
                      'text-gray-400'
                    }`} />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{agent.name}</h3>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      agent.status === 'active' ? 'bg-green-100 text-green-700' :
                      agent.status === 'in_game' ? 'bg-blue-100 text-blue-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {agent.status === 'in_game' ? 'Playing' : agent.status}
                    </span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => toggleAgent(agent.agent_id, agent.status)}
                    className={`p-2 rounded-lg transition-colors ${
                      agent.status === 'active' || agent.status === 'in_game'
                        ? 'bg-yellow-100 text-yellow-600 hover:bg-yellow-200'
                        : 'bg-green-100 text-green-600 hover:bg-green-200'
                    }`}
                    title={agent.status === 'active' ? 'Pause' : 'Start'}
                  >
                    {agent.status === 'active' || agent.status === 'in_game' ? (
                      <Pause className="w-4 h-4" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={() => deleteAgent(agent.agent_id)}
                    className="p-2 rounded-lg bg-red-100 text-red-600 hover:bg-red-200 transition-colors"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Strategy and settings */}
              <div className="flex flex-wrap gap-2 mb-4">
                <span className="text-xs px-2 py-1 bg-purple-100 text-purple-700 rounded-full">
                  {agent.strategy}
                </span>
                <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded-full">
                  {formatMON(agent.min_entry_fee_wei)} - {formatMON(agent.max_entry_fee_wei)} MON
                </span>
                {agent.preferred_games.length > 0 && (
                  <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded-full">
                    {agent.preferred_games.join(', ')}
                  </span>
                )}
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-100">
                <div>
                  <p className="text-xs text-gray-500">Games</p>
                  <p className="font-semibold text-gray-900">{agent.total_games}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Win Rate</p>
                  <p className="font-semibold text-gray-900">{agent.win_rate}%</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Profit</p>
                  <p className={`font-semibold flex items-center gap-1 ${
                    BigInt(agent.net_profit_wei) >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {BigInt(agent.net_profit_wei) >= 0 ? (
                      <TrendingUp className="w-3 h-3" />
                    ) : (
                      <TrendingDown className="w-3 h-3" />
                    )}
                    {formatMON(agent.net_profit_wei)} MON
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Agent Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-xl font-bold text-gray-900 mb-4">Create New Agent</h3>

            <div className="space-y-4">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Agent Name
                </label>
                <input
                  type="text"
                  value={newAgent.name}
                  onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
                  placeholder="e.g., Lucky Bot, Night Grinder"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>

              {/* Strategy */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Playing Strategy
                </label>
                <select
                  value={newAgent.strategy}
                  onChange={(e) => setNewAgent({ ...newAgent, strategy: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                >
                  <option value="conservative">Conservative - Safe plays, minimize losses</option>
                  <option value="balanced">Balanced - Mix of safe and risky</option>
                  <option value="aggressive">Aggressive - High risk, high reward</option>
                  <option value="random">Random - Unpredictable (for testing)</option>
                </select>
              </div>

              {/* Entry fee range */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Min Entry (MON)
                  </label>
                  <select
                    value={newAgent.min_entry_fee_wei}
                    onChange={(e) => setNewAgent({ ...newAgent, min_entry_fee_wei: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  >
                    <option value="1000000000000000">0.001 MON</option>
                    <option value="10000000000000000">0.01 MON</option>
                    <option value="100000000000000000">0.1 MON</option>
                    <option value="1000000000000000000">1 MON</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Entry (MON)
                  </label>
                  <select
                    value={newAgent.max_entry_fee_wei}
                    onChange={(e) => setNewAgent({ ...newAgent, max_entry_fee_wei: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  >
                    <option value="10000000000000000">0.01 MON</option>
                    <option value="100000000000000000">0.1 MON</option>
                    <option value="1000000000000000000">1 MON</option>
                    <option value="10000000000000000000">10 MON</option>
                    <option value="100000000000000000000">100 MON</option>
                  </select>
                </div>
              </div>

              {/* Game preferences */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Game Preferences (leave empty for all)
                </label>
                <div className="flex flex-wrap gap-2">
                  {['blackjack', 'claw', 'prediction', 'speed'].map((game) => (
                    <button
                      key={game}
                      onClick={() => {
                        const games = newAgent.preferred_games.includes(game)
                          ? newAgent.preferred_games.filter(g => g !== game)
                          : [...newAgent.preferred_games, game];
                        setNewAgent({ ...newAgent, preferred_games: games });
                      }}
                      className={`px-3 py-1 rounded-full text-sm transition-colors ${
                        newAgent.preferred_games.includes(game)
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {game}
                    </button>
                  ))}
                </div>
              </div>

              {/* Auto-join toggle */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-700">Auto-join games</p>
                  <p className="text-sm text-gray-500">Automatically join matching tournaments</p>
                </div>
                <button
                  onClick={() => setNewAgent({ ...newAgent, auto_join: !newAgent.auto_join })}
                  className={`w-12 h-6 rounded-full transition-colors ${
                    newAgent.auto_join ? 'bg-purple-600' : 'bg-gray-300'
                  }`}
                >
                  <div className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    newAgent.auto_join ? 'translate-x-6' : 'translate-x-0.5'
                  }`} />
                </button>
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowCreateModal(false)}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={createAgent}
                disabled={!newAgent.name}
                className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Create Agent
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserAgents;
