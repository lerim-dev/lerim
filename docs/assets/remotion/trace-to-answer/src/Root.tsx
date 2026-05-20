import { Composition } from "remotion";
import { TraceToAnswer } from "./TraceToAnswer";

export const RemotionRoot = () => {
  return (
    <Composition
      id="LerimTraceToAnswer"
      component={TraceToAnswer}
      durationInFrames={360}
      fps={30}
      width={1280}
      height={720}
    />
  );
};
