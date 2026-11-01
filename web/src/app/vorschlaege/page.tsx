import { redirect } from "next/navigation";

/** The suggestions now appear as tiles on the home page; old links land there. */
export default function Vorschlaege() {
  redirect("/");
}
