import React from 'react';
import { Bot } from 'lucide-react';
import UserAgents from '../components/UserAgents';

const AgentsPage = () => {
  return (
    <div className="min-h-screen bg-gray-50" data-testid="agents-page">
      {/* Hero */}
      <div className="bg-gradient-to-br from-white via-purple-50 to-white py-12 border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-[#836EF9] rounded-2xl mb-4">
              <Bot className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-3xl font-display font-bold text-gray-900 mb-2">
              My Agents
            </h1>
            <p className="text-gray-600 max-w-lg mx-auto">
              Create automated agents that play tournaments for you 24/7.
              Configure strategies, set entry limits, and earn passively.
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <UserAgents />
      </div>
    </div>
  );
};

export default AgentsPage;
