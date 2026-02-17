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
      alert(`Error: ${error}`);
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
      alert(`Error: ${error}`);
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
      alert(`Error: ${error}`);
    }
  };

  const handleCreateProposal = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsCreating(true);

    const formData = new FormData(e.currentTarget);
    const proposal = {
      type: formData.get("type"),
      symbol: formData.get("symbol"),
      quantity: parseFloat(formData.get("quantity") as string),
      orderType: formData.get("orderType"),
      price:
        formData.get("orderType") === "LIMIT"
          ? parseFloat(formData.get("price") as string)
          : undefined,
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
      alert(`Error: ${error}`);
    } finally {
      setIsCreating(false);
    }
  };

  if (error) {
    return (
      <AppShell>
        <div className="min-h-screen bg-gray-50 p-8">
          <div className="mx-auto max-w-7xl">
            <div className="rounded-lg bg-red-50 p-4 text-red-800">
              <h3 className="font-semibold">Error loading trades</h3>
              <p className="text-sm">{error.message}</p>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  const proposals = proposalsData?.proposals || [];

  return (
    <AppShell>
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="mx-auto max-w-7xl space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Trade Proposals
              </h1>
              <p className="text-sm text-gray-500">
                Manage and execute trade proposals
              </p>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              + Create Proposal
            </button>
          </div>

          {/* Filters */}
          <div className="flex gap-2">
            {["all", "validated", "approved", "executed", "rejected"].map(
              (status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`rounded-lg px-4 py-2 text-sm font-medium ${
                    statusFilter === status
                      ? "bg-blue-600 text-white"
                      : "bg-white text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </button>
              )
            )}
          </div>

          {/* Proposals List */}
          {!proposalsData ? (
            <div className="rounded-lg bg-white p-8 text-center shadow">
              <p className="text-gray-500">Loading...</p>
            </div>
          ) : proposals.length === 0 ? (
            <div className="rounded-lg bg-white p-8 text-center shadow">
              <p className="text-gray-500">No proposals found</p>
            </div>
          ) : (
            <div className="space-y-4">
              {proposals.map((proposal: any) => (
                <div
                  key={proposal.id}
                  className="rounded-lg bg-white p-6 shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <h3 className="text-lg font-semibold text-gray-900">
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
                          <span className="rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-800">
                            Auto-Approved
                          </span>
                        )}
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-4 md:grid-cols-4">
                        <div>
                          <p className="text-xs text-gray-500">Quantity</p>
                          <p className="text-sm font-medium text-gray-900">
                            {Number(proposal.quantity)}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">
                            {proposal.order_type}
                          </p>
                          <p className="text-sm font-medium text-gray-900">
                            {proposal.price
                              ? `$${Number(proposal.price).toLocaleString()}`
                              : "Market"}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">Notional</p>
                          <p className="text-sm font-medium text-gray-900">
                            ${Number(proposal.notional).toFixed(2)}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">Risk Score</p>
                          <p
                            className={`text-sm font-medium ${
                              Number(proposal.risk_score) > 70
                                ? "text-red-600"
                                : Number(proposal.risk_score) > 40
                                  ? "text-orange-600"
                                  : "text-green-600"
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
                          <p className="text-xs text-gray-500">Reasoning:</p>
                          <p className="text-sm text-gray-700">
                            {proposal.reasoning}
                          </p>
                        </div>
                      )}

                      <div className="mt-2 text-xs text-gray-500">
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
                            className="rounded-lg bg-green-600 px-3 py-1 text-sm font-medium text-white hover:bg-green-700"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(proposal.id)}
                            className="rounded-lg bg-red-600 px-3 py-1 text-sm font-medium text-white hover:bg-red-700"
                          >
                            Reject
                          </button>
                        </>
                      )}
                      {proposal.status === "approved" && (
                        <button
                          onClick={() => handleExecute(proposal.id)}
                          className="rounded-lg bg-blue-600 px-3 py-1 text-sm font-medium text-white hover:bg-blue-700"
                        >
                          Execute
                        </button>
                      )}
                      {proposal.status === "executed" && (
                        <span className="text-sm text-gray-500">
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
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h2 className="text-xl font-bold text-gray-900">
              Create Trade Proposal
            </h2>
            <form onSubmit={handleCreateProposal} className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Type
                </label>
                <select
                  name="type"
                  required
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                >
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Symbol
                </label>
                <input
                  type="text"
                  name="symbol"
                  required
                  placeholder="BTCUSDT"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Quantity
                </label>
                <input
                  type="number"
                  name="quantity"
                  required
                  step="0.00000001"
                  placeholder="0.001"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Order Type
                </label>
                <select
                  name="orderType"
                  required
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                >
                  <option value="MARKET">Market</option>
                  <option value="LIMIT">Limit</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Price (for limit orders)
                </label>
                <input
                  type="number"
                  name="price"
                  step="0.01"
                  placeholder="95000.00"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Reasoning
                </label>
                <textarea
                  name="reasoning"
                  rows={3}
                  placeholder="Why this trade?"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={isCreating}
                  className="flex-1 rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {isCreating ? "Creating..." : "Create Proposal"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 rounded-lg bg-gray-200 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
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
