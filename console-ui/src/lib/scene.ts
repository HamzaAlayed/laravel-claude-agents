export type Scene = "call" | "floor" | "spotlight";

export type SceneInput = {
  runActive: boolean;
  recorded: boolean;
  pending: number;
  spotlightOpen: boolean;
};

export function sceneOf(input: SceneInput): Scene {
  if (input.recorded) return "floor";
  if (!input.runActive) return "call";
  if (input.spotlightOpen && input.pending > 0) return "spotlight";
  return "floor";
}
