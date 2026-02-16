# Component Patterns & Best Practices

Common patterns used in the application.

---

## Page Layout

All pages should use AppShell:

```typescript
import { AppShell } from "@/components/ui/AppShell";

export default function MyPage() {
  return (
    <AppShell>
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="mx-auto max-w-7xl space-y-6">
          {/* Page content */}
        </div>
      </div>
    </AppShell>
  );
}
```

---

## Data Table Pattern

```typescript
export default function TablePage() {
  const { data, error, mutate } = useSWR("/api/endpoint", fetcher);

  if (error) {
    return (
      <AppShell>
        <div className="rounded-lg bg-red-50 p-4 text-red-800">
          <h3 className="font-semibold">Error</h3>
          <p className="text-sm">{error.message}</p>
        </div>
      </AppShell>
    );
  }

  if (!data) {
    return (
      <AppShell>
        <div className="rounded-lg bg-white p-8 text-center shadow">
          <p className="text-gray-500">Loading...</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-4">
        {data.items.map(item => (
          <div key={item.id} className="rounded-lg bg-white p-6 shadow">
            {/* Item content */}
          </div>
        ))}
      </div>
    </AppShell>
  );
}
```

---

## Modal Pattern

```typescript
const [showModal, setShowModal] = useState(false);

return (
  <>
    <button onClick={() => setShowModal(true)}>
      Open Modal
    </button>

    {showModal && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
        <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
          <h2 className="text-xl font-bold">Modal Title</h2>
          
          <div className="mt-4">
            {/* Modal content */}
          </div>

          <div className="mt-6 flex gap-2">
            <button
              onClick={handleSubmit}
              className="flex-1 rounded-lg bg-blue-600 py-2 text-white"
            >
              Submit
            </button>
            <button
              onClick={() => setShowModal(false)}
              className="flex-1 rounded-lg bg-gray-200 py-2"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    )}
  </>
);
```

---

## Form Pattern

```typescript
const [isSubmitting, setIsSubmitting] = useState(false);

const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
  e.preventDefault();
  setIsSubmitting(true);

  const formData = new FormData(e.currentTarget);
  const payload = {
    field1: formData.get("field1"),
    field2: parseFloat(formData.get("field2") as string),
  };

  try {
    const response = await fetch("/api/endpoint", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || "Request failed");
    }

    const result = await response.json();
    alert(result.message);
    mutate(); // Refresh SWR data
    e.currentTarget.reset(); // Clear form
  } catch (error) {
    alert(`Error: ${error}`);
  } finally {
    setIsSubmitting(false);
  }
};

return (
  <form onSubmit={handleSubmit} className="space-y-4">
    <div>
      <label className="block text-sm font-medium text-gray-700">
        Field 1
      </label>
      <input
        type="text"
        name="field1"
        required
        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
      />
    </div>

    <button
      type="submit"
      disabled={isSubmitting}
      className="w-full rounded-lg bg-blue-600 py-2 text-white disabled:opacity-50"
    >
      {isSubmitting ? "Submitting..." : "Submit"}
    </button>
  </form>
);
```

---

## Filter Pattern

```typescript
const [statusFilter, setStatusFilter] = useState("all");

const { data } = useSWR(
  statusFilter === "all"
    ? "/api/items"
    : `/api/items?status=${statusFilter}`,
  fetcher
);

return (
  <div>
    {/* Filter Buttons */}
    <div className="flex gap-2 mb-6">
      {["all", "active", "pending", "completed"].map(status => (
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
      ))}
    </div>

    {/* Filtered Data */}
    <div className="space-y-4">
      {data?.items.map(item => (
        <div key={item.id}>{/* Item */}</div>
      ))}
    </div>
  </div>
);
```

---

## Status Badge Usage

```typescript
import { StatusBadge } from "@/components/ui/StatusBadge";

// Default variant (auto-colored based on status)
<StatusBadge status="approved" />
<StatusBadge status="rejected" />

// Explicit variant
<StatusBadge status="buy" variant="success" />
<StatusBadge status="sell" variant="error" />
<StatusBadge status="pending" variant="warning" />
```

---

## Empty State Usage

```typescript
import { EmptyState } from "@/components/ui/EmptyState";

{data.length === 0 && (
  <EmptyState
    title="No trades found"
    description="Create your first trade proposal to get started"
  />
)}
```

---

## Grid Layout

```typescript
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {items.map(item => (
    <div key={item.id} className="rounded-lg bg-white p-6 shadow">
      {/* Card content */}
    </div>
  ))}
</div>
```

---

## Stats Display

```typescript
<div className="grid grid-cols-2 md:grid-cols-4 gap-4">
  <div>
    <p className="text-xs text-gray-500">Total Balance</p>
    <p className="text-2xl font-bold text-gray-900">
      ${balance.total.toLocaleString()}
    </p>
  </div>
  
  <div>
    <p className="text-xs text-gray-500">Available</p>
    <p className="text-2xl font-bold text-green-600">
      ${balance.available.toLocaleString()}
    </p>
  </div>
</div>
```

---

## Action Buttons

```typescript
// Primary Action
<button className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
  Execute
</button>

// Success Action
<button className="rounded-lg bg-green-600 px-3 py-1 text-sm font-medium text-white hover:bg-green-700">
  Approve
</button>

// Danger Action
<button className="rounded-lg bg-red-600 px-3 py-1 text-sm font-medium text-white hover:bg-red-700">
  Reject
</button>

// Secondary Action
<button className="rounded-lg bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300">
  Cancel
</button>
```

---

## Confirmation Pattern

```typescript
const handleAction = async () => {
  if (!confirm("Are you sure you want to proceed?")) {
    return;
  }

  try {
    await fetch("/api/action", { method: "POST" });
    alert("Action completed successfully!");
    mutate();
  } catch (error) {
    alert(`Error: ${error}`);
  }
};
```
