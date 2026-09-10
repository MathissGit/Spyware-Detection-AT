"""Tests GUI widgets : ProgressStep, DeviceCard, StepIndicator, Toast."""
import customtkinter as ctk
import pytest


@pytest.fixture
def root():
    r = ctk.CTk()
    r.withdraw()
    r.update()
    yield r
    r.destroy()


class TestProgressStepStates:
    def test_pending_initial(self, root):
        from gui.widgets.progress_step import ProgressStep
        ps = ProgressStep(root, "Test", index=0)
        ps.pack()
        ps.update()
        assert ps.state == "pending"
        ps.destroy()

    def test_active(self, root):
        from gui.widgets.progress_step import ProgressStep
        ps = ProgressStep(root, "Test", index=0)
        ps.pack()
        ps.set_state("active", "1.2s")
        ps.update()
        assert ps.state == "active"
        ps.destroy()

    def test_done(self, root):
        from gui.widgets.progress_step import ProgressStep
        ps = ProgressStep(root, "Test", index=0)
        ps.pack()
        ps.set_state("done", "2.5s")
        ps.update()
        assert ps.state == "done"
        ps.destroy()

    def test_error(self, root):
        from gui.widgets.progress_step import ProgressStep
        ps = ProgressStep(root, "Test", index=0)
        ps.pack()
        ps.set_state("error", "0.1s")
        ps.update()
        assert ps.state == "error"
        ps.destroy()

    def test_invalid_state_ignored(self, root):
        from gui.widgets.progress_step import ProgressStep
        ps = ProgressStep(root, "Test", index=0)
        ps.pack()
        ps.set_state("invalid")
        assert ps.state == "pending"
        ps.destroy()

    def test_reset(self, root):
        from gui.widgets.progress_step import ProgressStep
        ps = ProgressStep(root, "Test", index=0)
        ps.pack()
        ps.set_state("active")
        ps.reset()
        assert ps.state == "pending"
        ps.destroy()

    def test_all_states(self, root):
        from gui.widgets.progress_step import ProgressStep
        ps = ProgressStep(root, "Test", index=0)
        ps.pack()
        for state in ProgressStep.STATES:
            ps.set_state(state, "1.0s")
            assert ps.state == state
        ps.destroy()


class TestDeviceCardSelect:
    def test_select_deselect(self, root):
        from gui.widgets.device_card import DeviceCard
        card = DeviceCard(root, label="Test")
        card.pack()
        card.update()
        card.select()
        assert card._selected is True
        card.deselect()
        assert card._selected is False
        card.destroy()

    def test_click_calls_command(self, root):
        from gui.widgets.device_card import DeviceCard
        called = {"n": 0}
        card = DeviceCard(root, label="Test",
                          command=lambda: called.update({"n": called["n"] + 1}))
        card.pack()
        card.update()
        card._on_click()
        assert called["n"] == 1
        card.destroy()

    def test_hover(self, root):
        from gui.widgets.device_card import DeviceCard
        card = DeviceCard(root, label="Test")
        card.pack()
        card.update()
        card._on_enter()
        card._on_leave()
        assert card._selected is False
        card.destroy()

    def test_hover_no_change_when_selected(self, root):
        from gui.widgets.device_card import DeviceCard
        card = DeviceCard(root, label="Test")
        card.pack()
        card.select()
        card.update()
        card._on_enter()
        card._on_leave()
        assert card._selected is True
        card.destroy()


class TestStepIndicator:
    def test_set_step(self, root):
        from gui.widgets.step_indicator import StepIndicator
        steps = ["Step 1", "Step 2", "Step 3"]
        si = StepIndicator(root, steps)
        si.pack()
        si.update()
        si.set_step(1)
        assert si.current == 1
        si.destroy()

    def test_reset(self, root):
        from gui.widgets.step_indicator import StepIndicator
        steps = ["A", "B"]
        si = StepIndicator(root, steps)
        si.pack()
        si.set_step(1)
        si.reset()
        si.update()
        assert si.current == -1
        si.destroy()

    def test_same_step_noop(self, root):
        from gui.widgets.step_indicator import StepIndicator
        steps = ["A", "B", "C"]
        si = StepIndicator(root, steps)
        si.pack()
        si.set_step(1)
        assert si.current == 1
        si.set_step(1)
        assert si.current == 1
        si.destroy()

    def test_step_updates_dots(self, root):
        from gui.widgets.step_indicator import StepIndicator
        steps = ["A", "B", "C"]
        si = StepIndicator(root, steps)
        si.pack()
        si.set_step(2)
        si.update()
        assert si.current == 2
        si.destroy()


class TestToastBehavior:
    def test_creates_and_destroyed(self, root):
        from gui.widgets.toast import Toast
        toast = Toast(root, "Test message", duration=100)
        toast.update()
        assert toast.winfo_exists()
        toast.destroy()
