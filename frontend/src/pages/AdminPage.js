import React, { useState, useEffect } from 'react';
import { 
  getArenas, createArena, closeArena, requestFinalizeSignature, 
  recordFinalize, formatMON, parseMON, getExplorerUrl 
} from '../services/api';
import { useWallet } from '../context/WalletContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { 
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue 
} from '../components/ui/select';
import { 
  Plus, Lock, Trophy, Loader2, CheckCircle, AlertCircle, 
  ExternalLink, Settings, Shield 
} from 'lucide-react';
import { toast } from 'sonner';

const AdminPage = () => {
  const { isConnected, address, connect } = useWallet();
  const [arenas, setArenas] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Create Arena Form
  const [createForm, setCreateForm] = useState({
    name: '',
    entry_fee: '0.1',
    max_players: '8',
    protocol_fee_bps: '250',
  });
  const [creating, setCreating] = useState(false);

  // Finalize Form
  const [selectedArena, setSelectedArena] = useState(null);
  const [winners, setWinners] = useState(['', '']);
  const [amounts, setAmounts] = useState(['', '']);
  const [signatureData, setSignatureData] = useState(null);
  const [requesting, setRequesting] = useState(false);
  const [finalizing, setFinalizing] = useState(false);

  useEffect(() => {
    fetchArenas();
  }, []);

  const fetchArenas = async () => {
    try {
      const data = await getArenas();
      setArenas(data);
    } catch (error) {
      console.error('Failed to fetch arenas:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateArena = async (e) => {
    e.preventDefault();
    setCreating(true);
    
    try {
      const arenaData = {
        name: createForm.name,
        entry_fee: parseMON(createForm.entry_fee),
        max_players: parseInt(createForm.max_players),
        protocol_fee_bps: parseInt(createForm.protocol_fee_bps),
        treasury: address || '0x0000000000000000000000000000000000000000',
      };
      
      const newArena = await createArena(arenaData);
      toast.success(`Arena "${newArena.name}" created successfully!`);
      
      setCreateForm({ name: '', entry_fee: '0.1', max_players: '8', protocol_fee_bps: '250' });
      await fetchArenas();
    } catch (error) {
      console.error('Failed to create arena:', error);
      toast.error(error.response?.data?.detail || 'Failed to create arena');
    } finally {
      setCreating(false);
    }
  };

  const handleCloseArena = async (arenaAddress) => {
    try {
      await closeArena(arenaAddress);
      toast.success('Arena registration closed');
      await fetchArenas();
    } catch (error) {
      console.error('Failed to close arena:', error);
      toast.error(error.response?.data?.detail || 'Failed to close arena');
    }
  };

  const handleRequestSignature = async () => {
    if (!selectedArena) return;
    
    const validWinners = winners.filter(w => w.trim());
    const validAmounts = amounts.filter((a, i) => winners[i]?.trim() && a.trim());
    
    if (validWinners.length === 0) {
      toast.error('Please add at least one winner');
      return;
    }

    setRequesting(true);
    try {
      const data = await requestFinalizeSignature(
        selectedArena.address,
        validWinners,
        validAmounts.map(a => parseMON(a))
      );
      setSignatureData(data);
      toast.success('Signature received from OpenClaw agent!');
    } catch (error) {
      console.error('Failed to request signature:', error);
      toast.error(error.response?.data?.detail || 'Failed to request signature');
    } finally {
      setRequesting(false);
    }
  };

  const handleFinalize = async () => {
    if (!signatureData) return;
    
    setFinalizing(true);
    try {
      // In production: call smart contract finalize() with signature
      // const tx = await contract.finalize(winners, amounts, signature);
      // await tx.wait();
      
      const mockTxHash = '0x' + Array(64).fill(0).map(() => Math.floor(Math.random() * 16).toString(16)).join('');
      
      await recordFinalize(
        signatureData.arena_address,
        mockTxHash,
        signatureData.winners,
        signatureData.amounts
      );
      
      toast.success('Tournament finalized successfully!');
      setSignatureData(null);
      setSelectedArena(null);
      setWinners(['', '']);
      setAmounts(['', '']);
      await fetchArenas();
    } catch (error) {
      console.error('Failed to finalize:', error);
      toast.error(error.response?.data?.detail || 'Failed to finalize');
    } finally {
      setFinalizing(false);
    }
  };

  const closedArenas = arenas.filter(a => a.is_closed && !a.is_finalized);
  const openArenas = arenas.filter(a => !a.is_closed && !a.is_finalized);

  if (!isConnected) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" data-testid="admin-page">
        <div className="text-center max-w-md mx-auto px-4">
          <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Shield className="w-8 h-8 text-[#836EF9]" />
          </div>
          <h2 className="font-heading text-2xl font-bold text-gray-900 mb-2">Admin Access Required</h2>
          <p className="text-gray-500 mb-6">Connect your wallet to access the admin panel</p>
          <Button onClick={connect} className="btn-primary" data-testid="admin-connect-btn">
            Connect Wallet
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="admin-page">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 py-8">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-[#836EF9] rounded-xl flex items-center justify-center">
              <Settings className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-heading text-3xl font-bold text-gray-900">Admin Panel</h1>
              <p className="text-gray-500">Manage tournaments and finalize results</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid lg:grid-cols-2 gap-8">
          {/* Create Arena */}
          <div className="admin-section" data-testid="create-arena-section">
            <h3 className="admin-section-title">
              <Plus className="w-5 h-5 text-[#836EF9]" />
              Create New Arena
            </h3>
            
            <form onSubmit={handleCreateArena} className="space-y-4">
              <div>
                <Label htmlFor="name">Arena Name</Label>
                <Input
                  id="name"
                  placeholder="e.g., Weekend Showdown #1"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  className="form-input mt-1"
                  required
                  data-testid="arena-name-input"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="entry_fee">Entry Fee (MON)</Label>
                  <Input
                    id="entry_fee"
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="0.1"
                    value={createForm.entry_fee}
                    onChange={(e) => setCreateForm({ ...createForm, entry_fee: e.target.value })}
                    className="form-input mt-1"
                    required
                    data-testid="entry-fee-input"
                  />
                </div>
                <div>
                  <Label htmlFor="max_players">Max Players</Label>
                  <Select
                    value={createForm.max_players}
                    onValueChange={(value) => setCreateForm({ ...createForm, max_players: value })}
                  >
                    <SelectTrigger className="mt-1" data-testid="max-players-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[4, 8, 16, 32].map((n) => (
                        <SelectItem key={n} value={n.toString()}>{n} Players</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div>
                <Label htmlFor="protocol_fee">Protocol Fee (basis points)</Label>
                <Select
                  value={createForm.protocol_fee_bps}
                  onValueChange={(value) => setCreateForm({ ...createForm, protocol_fee_bps: value })}
                >
                  <SelectTrigger className="mt-1" data-testid="protocol-fee-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="100">1%</SelectItem>
                    <SelectItem value="250">2.5%</SelectItem>
                    <SelectItem value="500">5%</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <Button 
                type="submit" 
                className="w-full btn-primary"
                disabled={creating || !createForm.name}
                data-testid="create-arena-submit"
              >
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4 mr-2" />
                    Create Arena
                  </>
                )}
              </Button>
            </form>
          </div>

          {/* Close Registration */}
          <div className="admin-section" data-testid="close-arena-section">
            <h3 className="admin-section-title">
              <Lock className="w-5 h-5 text-[#836EF9]" />
              Close Registration
            </h3>
            
            {openArenas.length > 0 ? (
              <div className="space-y-3">
                {openArenas.map((arena) => (
                  <div key={arena.address} className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-900 truncate">{arena.name}</p>
                      <p className="text-sm text-gray-500">{arena.players?.length || 0} / {arena.max_players} players</p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleCloseArena(arena.address)}
                      className="ml-4 border-orange-200 text-orange-600 hover:bg-orange-50"
                      data-testid={`close-btn-${arena.address}`}
                    >
                      <Lock className="w-4 h-4 mr-1" />
                      Close
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Lock className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                No open arenas to close
              </div>
            )}
          </div>

          {/* Finalize Tournament */}
          <div className="admin-section lg:col-span-2" data-testid="finalize-section">
            <h3 className="admin-section-title">
              <Trophy className="w-5 h-5 text-[#836EF9]" />
              Finalize Tournament
            </h3>
            
            {closedArenas.length > 0 ? (
              <div className="space-y-6">
                {/* Select Arena */}
                <div>
                  <Label>Select Arena to Finalize</Label>
                  <Select
                    value={selectedArena?.address || ''}
                    onValueChange={(value) => {
                      const arena = closedArenas.find(a => a.address === value);
                      setSelectedArena(arena);
                      setSignatureData(null);
                      if (arena) {
                        // Pre-fill winners from players
                        setWinners(arena.players?.slice(0, 2) || ['', '']);
                        // Calculate default amounts (50/50 split after fee)
                        const pool = BigInt(arena.entry_fee) * BigInt(arena.players?.length || 0);
                        const fee = (pool * BigInt(arena.protocol_fee_bps)) / BigInt(10000);
                        const net = pool - fee;
                        const first = (net * BigInt(60)) / BigInt(100);
                        const second = net - first;
                        setAmounts([formatMON(first.toString()), formatMON(second.toString())]);
                      }
                    }}
                  >
                    <SelectTrigger className="mt-1" data-testid="finalize-arena-select">
                      <SelectValue placeholder="Select an arena..." />
                    </SelectTrigger>
                    <SelectContent>
                      {closedArenas.map((arena) => (
                        <SelectItem key={arena.address} value={arena.address}>
                          {arena.name} ({arena.players?.length || 0} players)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {selectedArena && (
                  <>
                    {/* Arena Info */}
                    <div className="bg-purple-50 rounded-xl p-4">
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <p className="text-gray-500">Prize Pool</p>
                          <p className="font-bold text-[#836EF9]">
                            {formatMON((BigInt(selectedArena.entry_fee) * BigInt(selectedArena.players?.length || 0)).toString())} MON
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-500">Players</p>
                          <p className="font-bold text-gray-900">{selectedArena.players?.length || 0}</p>
                        </div>
                        <div>
                          <p className="text-gray-500">Protocol Fee</p>
                          <p className="font-bold text-gray-900">{selectedArena.protocol_fee_bps / 100}%</p>
                        </div>
                      </div>
                    </div>

                    {/* Winners Input */}
                    <div className="space-y-3">
                      <Label>Winners & Payouts</Label>
                      {winners.map((winner, index) => (
                        <div key={index} className="grid grid-cols-3 gap-3">
                          <div className="col-span-2">
                            <Input
                              placeholder={`Winner ${index + 1} address`}
                              value={winner}
                              onChange={(e) => {
                                const newWinners = [...winners];
                                newWinners[index] = e.target.value;
                                setWinners(newWinners);
                              }}
                              className="form-input font-mono text-sm"
                              data-testid={`winner-input-${index}`}
                            />
                          </div>
                          <Input
                            type="number"
                            step="0.001"
                            placeholder="Amount (MON)"
                            value={amounts[index]}
                            onChange={(e) => {
                              const newAmounts = [...amounts];
                              newAmounts[index] = e.target.value;
                              setAmounts(newAmounts);
                            }}
                            className="form-input"
                            data-testid={`amount-input-${index}`}
                          />
                        </div>
                      ))}
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setWinners([...winners, '']);
                          setAmounts([...amounts, '']);
                        }}
                        className="text-[#836EF9]"
                        data-testid="add-winner-btn"
                      >
                        <Plus className="w-4 h-4 mr-1" />
                        Add Winner
                      </Button>
                    </div>

                    {/* Request Signature */}
                    {!signatureData ? (
                      <Button
                        onClick={handleRequestSignature}
                        disabled={requesting}
                        className="w-full btn-primary"
                        data-testid="request-signature-btn"
                      >
                        {requesting ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Requesting Signature from OpenClaw...
                          </>
                        ) : (
                          'Request Finalize Signature'
                        )}
                      </Button>
                    ) : (
                      <div className="space-y-4">
                        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
                          <div className="flex items-start gap-3">
                            <CheckCircle className="w-5 h-5 text-green-500 mt-0.5" />
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-green-700">Signature Received</p>
                              <p className="text-sm text-green-600 mt-1">
                                Operator: <span className="font-mono">{signatureData.operator_address?.slice(0, 10)}...</span>
                              </p>
                              <p className="text-sm text-green-600">
                                Nonce: {signatureData.nonce}
                              </p>
                            </div>
                          </div>
                        </div>

                        <Button
                          onClick={handleFinalize}
                          disabled={finalizing}
                          className="w-full bg-green-600 hover:bg-green-700 text-white"
                          data-testid="finalize-btn"
                        >
                          {finalizing ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              Finalizing...
                            </>
                          ) : (
                            <>
                              <Trophy className="w-4 h-4 mr-2" />
                              Finalize & Distribute Prizes
                            </>
                          )}
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <AlertCircle className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                No closed arenas ready for finalization
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminPage;
