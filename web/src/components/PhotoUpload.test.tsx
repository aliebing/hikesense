import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({
  session: null as null | { user: { id: string } },
  prepareUpload: vi.fn(),
  uploadOwnPhoto: vi.fn(),
  blocked: false,
  report: vi.fn(),
}));
vi.mock("../lib/auth", () => ({
  checkBlocked: async () => h.blocked,
  onBlocked: () => () => {},
  reportBlocked: h.report,
  useSession: () => ({ session: h.session, loading: false }),
  getBrowserSupabase: () => ({}),
}));
vi.mock("../lib/photo", () => ({ prepareUpload: h.prepareUpload, uploadOwnPhoto: h.uploadOwnPhoto }));

import { renderWithLocale } from "../test-utils";
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
  h.prepareUpload.mockRejectedValue(Object.assign(new Error("x"), { code: "tooBig" }));
  render(<PhotoUpload trailId="t1" onUploaded={() => {}} />);
  await userEvent.upload(screen.getByLabelText("Foto auswählen"), new File(["y"], "a.jpg", { type: "image/jpeg" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Foto ist größer als 10 MB");
  expect(h.uploadOwnPhoto).not.toHaveBeenCalled();
});

it("English: the rejection message is English", async () => {
  h.session = { user: { id: "u1" } };
  h.prepareUpload.mockRejectedValue(Object.assign(new Error("x"), { code: "tooBig" }));
  renderWithLocale(<PhotoUpload trailId="t1" onUploaded={() => {}} />, "en");
  expect(screen.getByRole("button", { name: "Add own photo" })).toBeInTheDocument();
  await userEvent.upload(screen.getByLabelText("Choose photo"), new File(["y"], "a.jpg", { type: "image/jpeg" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("The photo is larger than 10 MB");
});

it("an unknown upload error gets the generic text, never the technical message", async () => {
  h.session = { user: { id: "u1" } };
  h.prepareUpload.mockRejectedValue(new Error("boom"));
  renderWithLocale(<PhotoUpload trailId="t1" onUploaded={() => {}} />, "en");
  await userEvent.upload(screen.getByLabelText("Choose photo"), new File(["y"], "a.jpg", { type: "image/jpeg" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Upload did not work");
});

it("a refused upload of a blocked account signs it out", async () => {
  h.session = { user: { id: "u1" } };
  h.blocked = true;
  h.prepareUpload.mockResolvedValue(new Blob(["x"]));
  h.uploadOwnPhoto.mockRejectedValue(Object.assign(new Error("x"), { code: "upload" }));
  render(<PhotoUpload trailId="t1" onUploaded={() => {}} />);
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await userEvent.upload(input, new File(["x"], "a.jpg", { type: "image/jpeg" }));
  await waitFor(() => expect(h.report).toHaveBeenCalledTimes(1));
  h.blocked = false;
});
