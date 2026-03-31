"use client";

import { useState } from "react";
import useSWR from "swr";
import { AppShell } from "@/components/ui/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function TradesPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [isCreating, setIsCreating] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Fetch proposals
  const {
    data: proposalsData,
    error,
    mutate,
  } = useSWR(
    statusFilter === "all"
      ? "/api/trades/proposals?limit=100"
      : `/api/trades/proposals?status=${statusFilter}&limit=100`,
    fetcher,
    {
      refreshInterval: 15000, // Refresh every 15 seconds
    }
  );

  const handleApprove = async (proposalId: string) => {
    if (!confirm("Are you sure you want to approve this trade?")) return;

    try {
      const response = await fetch(`/api/trades/proposals/${proposalId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "approve" }),
      });

      if (!response.ok) throw new Error("Failed to approve");

      alert("Trade approved successfully!");
      mutate();
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const handleReject = async (proposalId: string) => {
    const notes = prompt("Rejection reason (optional):");

    try {
      const response = await fetch(`/api/trades/proposals/${proposalId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reject", notes }),
      });

      if (!response.ok) throw new Error("Failed to reject");

      alert("Trade rejected successfully!");
      mutate();
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const handleExecute = async (proposalId: string) => {
    if (!confirm("Are you sure you want to execute this trade?")) return;

    try {
      const response = await fetch("/api/trades/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proposalId }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to execute");
      }

      const data = await response.json();
      const orderId = data.execution?.orderId ?? data.order_id ?? data.id ?? "confirmed";
      alert(`Trade executed successfully! Order ID: ${orderId}`);
      mutate();
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const handleCreateProposal = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsCreating(true);

    const formData = new FormData(e.currentTarget);
    const rawQuantity = parseFloat(formData.get("quantity") as string);
    const rawPrice = parseFloat(formData.get("price") as string);

    if (!Number.isFinite(rawQuantity) || rawQuantity <= 0) {
      alert("Invalid quantity: must be a positive number");
      setIsCreating(false);
      return;
    }

    if (formData.get("orderType") === "LIMIT" && (!Number.isFinite(rawPrice) || rawPrice <= 0)) {
      alert("Invalid price: must be a positive number for limit orders");
      setIsCreating(false);
      return;
    }

    const proposal = {
      type: formData.get("type"),
      symbol: formData.get("symbol"),
      quantity: rawQuantity,
      orderType: formData.get("orderType"),
      price: formData.get("orderType") === "LIMIT" ? rawPrice : undefined,
      reasoning: formData.get("reasoning"),
    };

    try {
      const response = await fetch("/api/trades/proposals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(proposal),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to create proposal");
      }

      const data = await response.json();
      alert(data.message);
      setShowCreateModal(false);
      mutate();
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsCreating(false);
    }
  };

  if (error) {
    return (
      <AppShell title="Trade Proposals">
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-red-300">
          <h3 className="font-semibold">Error loading trades</h3>
          <p className="text-sm">{error.message}</p>
        </div>
      </AppShell>
    );
  }

  const proposals = proposalsData?.proposals || [];

  return (
    <AppShell
      title="Trade Proposals"
      description="Manage and execute trade proposals"
      actions={
        <button
          onClick={() => setShowCreateModal(true)}
          className="rounded-lg bg-emerald-500/20 px-4 py-2 text-sm font-medium text-emerald-400 transition-colors hover:bg-emerald-500/30"
        >
          + Create Proposal
        </button>
      }
    >
      <div className="space-y-6">
        {/* Filters */}
        <div className="flex flex-wrap gap-2">
          {["all", "validated", "approved", "executed", "rejected"].map(
            (status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  statusFilter === status
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    : "border border-white/10 text-slate-400 hover:bg-white/5 hover:text-white"
                }`}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </button>
            )
          )}
        </div>

        {/* Proposals List */}
        {!proposalsData ? (
          <div className="rounded-xl border border-white/10 bg-white/5 p-8 text-center">
            <p className="text-slate-400">Loading...</p>
          </div>
        ) : proposals.length === 0 ? (
          <div className="rounded-xl border border-white/10 bg-white/5 p-8 text-center">
            <p className="text-slate-400">No proposals found</p>
          </div>
        ) : (
          <div className="space-y-4">
            {proposals.map((proposal: any) => (
              <div
                key={proposal.id}
                className="rounded-xl border border-white/10 bg-white/[0.03] p-6 transition-colors hover:border-white/20"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-semibold text-white">
                        {proposal.symbol}
                      </h3>
                      <StatusBadge
                        status={proposal.type}
                        variant={
                          proposal.type === "buy" ? "success" : "error"
                        }
                      />
                      <StatusBadge status={proposal.status} />
                      {proposal.auto_approved && (
                        <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-400 border border-emerald-500/20">
                          Auto-Approved
                        </span>
                      )}
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-4 md:grid-cols-4">
                      <div>
                        <p className="text-xs text-slate-500">Quantity</p>
                        <p className="text-sm font-medium text-white">
                          {Number(proposal.quantity)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">
                          {proposal.order_type}
                        </p>
                        <p className="text-sm font-medium text-white">
                          {proposal.price
                            ? `$${Number(proposal.price).toLocaleString()}`
                            : "Market"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Notional</p>
                        <p className="text-sm font-medium text-white">
                          ${Number(proposal.notional).toFixed(2)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Risk Score</p>
                        <p
                          className={`text-sm font-medium ${
                            Number(proposal.risk_score) > 70
                              ? "text-red-400"
                              : Number(proposal.risk_score) > 40
                                ? "text-amber-400"
                                : "text-emerald-400"
                          }`}
                        >
                          {proposal.risk_score
                            ? Number(proposal.risk_score).toFixed(0)
                            : "N/A"}
                          /100
                        </p>
                      </div>
                    </div>

                    {proposal.reasoning && (
                      <div className="mt-3">
                        <p className="text-xs text-slate-500">Reasoning:</p>
                        <p className="text-sm text-slate-300">
                          {proposal.reasoning}
                        </p>
                      </div>
                    )}

                    <div className="mt-2 text-xs text-slate-500">
                      Created:{" "}
                      {new Date(proposal.created_at).toLocaleString()}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="ml-4 flex gap-2">
                    {proposal.status === "validated" && (
                      <>
                        <button
                          onClick={() => handleApprove(proposal.id)}
                          className="rounded-lg bg-emerald-500/20 px-3 py-1 text-sm font-medium text-emerald-400 hover:bg-emerald-500/30 border border-emerald-500/20"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleReject(proposal.id)}
                          className="rounded-lg bg-red-500/20 px-3 py-1 text-sm font-medium text-red-400 hover:bg-red-500/30 border border-red-500/20"
                        >
                          Reject
                        </button>
                      </>
                    )}
                    {proposal.status === "approved" && (
                      <button
                        onClick={() => handleExecute(proposal.id)}
                        className="rounded-lg bg-blue-500/20 px-3 py-1 text-sm font-medium text-blue-400 hover:bg-blue-500/30 border border-blue-500/20"
                      >
                        Execute
                      </button>
                    )}
                    {proposal.status === "executed" && (
                      <span className="text-sm text-slate-500">
                        Order #{proposal.binance_order_id}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-white/10 bg-slate-900 p-6 shadow-2xl">
            <h2 className="text-xl font-bold text-white">
              Create Trade Proposal
            </h2>
            <form onSubmit={handleCreateProposal} className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300">
                  Type
                </label>
                <select
                  name="type"
                  required
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-white"
                >
                  <option value="buy" className="bg-slate-900">Buy</option>
                  <option value="sell" className="bg-slate-900">Sell</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300">
                  Symbol
                </label>
                <input
                  type="text"
                  name="symbol"
                  required
                  placeholder="BTCUSDT"
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-white placeholder:text-slate-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300">
                  Quantity
                </label>
                <input
                  type="number"
                  name="quantity"
                  required
                  step="0.00000001"
                  placeholder="0.001"
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-white placeholder:text-slate-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300">
                  Order Type
                </label>
                <select
                  name="orderType"
                  required
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-white"
                >
                  <option value="MARKET" className="bg-slate-900">Market</option>
                  <option value="LIMIT" className="bg-slate-900">Limit</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300">
                  Price (for limit orders)
                </label>
                <input
                  type="number"
                  name="price"
                  step="0.01"
                  placeholder="95000.00"
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-white placeholder:text-slate-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300">
                  Reasoning
                </label>
                <textarea
                  name="reasoning"
                  rows={3}
                  placeholder="Why this trade?"
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-white placeholder:text-slate-500"
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={isCreating}
                  className="flex-1 rounded-lg bg-emerald-500/20 py-2 text-sm font-medium text-emerald-400 hover:bg-emerald-500/30 disabled:opacity-50 border border-emerald-500/20"
                >
                  {isCreating ? "Creating..." : "Create Proposal"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 rounded-lg border border-white/10 py-2 text-sm font-medium text-slate-400 hover:bg-white/5"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
