import { beforeEach, describe, expect, it } from "vitest";
import { useNotificationStore } from "../notificationStore";

describe("useNotificationStore", () => {
  beforeEach(() => {
    // Reset store state between tests
    useNotificationStore.setState({ notifications: [] });
  });

  it("add appends a notification with id and timestamp", () => {
    const { add } = useNotificationStore.getState();
    add({ type: "info", title: "Test" });
    const { notifications } = useNotificationStore.getState();
    expect(notifications).toHaveLength(1);
    expect(notifications[0].title).toBe("Test");
    expect(notifications[0].id).toBeTruthy();
    expect(notifications[0].timestamp).toBeGreaterThan(0);
  });

  it("add caps at 20 notifications", () => {
    const { add } = useNotificationStore.getState();
    for (let i = 0; i < 25; i++) {
      add({ type: "info", title: `Notification ${i}` });
    }
    const { notifications } = useNotificationStore.getState();
    expect(notifications).toHaveLength(20);
    // First 5 should have been removed (slice keeps last 20)
    expect(notifications[0].title).toBe("Notification 5");
  });

  it("dismiss removes by id", () => {
    const { add } = useNotificationStore.getState();
    add({ type: "success", title: "A" });
    add({ type: "error", title: "B" });

    const { notifications } = useNotificationStore.getState();
    const idToRemove = notifications[0].id;
    useNotificationStore.getState().dismiss(idToRemove);

    const updated = useNotificationStore.getState().notifications;
    expect(updated).toHaveLength(1);
    expect(updated[0].title).toBe("B");
  });

  it("multiple adds and dismisses maintain correct state", () => {
    const { add } = useNotificationStore.getState();
    add({ type: "info", title: "First" });
    add({ type: "warning", title: "Second" });
    add({ type: "error", title: "Third" });

    let { notifications } = useNotificationStore.getState();
    expect(notifications).toHaveLength(3);

    // Dismiss middle one
    useNotificationStore.getState().dismiss(notifications[1].id);
    notifications = useNotificationStore.getState().notifications;
    expect(notifications).toHaveLength(2);
    expect(notifications[0].title).toBe("First");
    expect(notifications[1].title).toBe("Third");
  });
});
