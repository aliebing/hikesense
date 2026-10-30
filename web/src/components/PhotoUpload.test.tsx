import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({
  session: null as null | { user: { id: string } },
  prepareUpload: vi.fn(),
  uploadOwnPhoto: vi.fn(),
}));
vi.mock("../lib/auth", () => ({
  useSession: () => ({ session: h.session, loading: false }),
  getBrowserSupabase: () => ({}),
}));
vi.mock("../lib/photo", () => ({ prepareUpload: h.prepareUpload, uploadOwnPhoto: h.uploadOwnPhoto }));

import PhotoUpload from "./PhotoUpload";

beforeEach(() => {
  h.prepareUpload.mockReset();
  h.uploadOwnPhoto.mockReset();
});

it("upload button only with session", () => {
  h.session = null;
  const { rerender } = render(<PhotoUpload trailId="t1" onUploaded={() => {}} />);
  expect(screen.queryByRole("button", { name: /Eigenes Foto/ })).toBeNull();
  h.session = { user: { id: "u1" } };
  rerender(<PhotoUpload trailId="t1" onUploaded={() => {}} />);
  expect(screen.getByRole("button", { name: "Eigenes Foto hinzufügen" })).toBeInTheDocument();
});

it("uploads the prepared blob under the user and trail", async () => {
  h.session = { user: { id: "u1" } };
  const blob = new Blob(["x"]);
  h.prepareUpload.mockResolvedValue(blob);
  h.uploadOwnPhoto.mockResolvedValue(undefined);
  const done = vi.fn();
  render(<PhotoUpload trailId="t1" onUploaded={done} />);
  await userEvent.upload(screen.getByLabelText("Foto auswählen"), new File(["y"], "a.jpg", { type: "image/jpeg" }));
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(h.uploadOwnPhoto).toHaveBeenCalledWith({}, "u1", "t1", blob);
});

it("shows the rejection message and uploads nothing", async () => {
  h.session = { user: { id: "u1" } };
  h.prepareUpload.mockRejectedValue(new Error("Foto ist größer als 10 MB"));
  render(<PhotoUpload trailId="t1" onUploaded={() => {}} />);
  await userEvent.upload(screen.getByLabelText("Foto auswählen"), new File(["y"], "a.jpg", { type: "image/jpeg" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Foto ist größer als 10 MB");
  expect(h.uploadOwnPhoto).not.toHaveBeenCalled();
});
