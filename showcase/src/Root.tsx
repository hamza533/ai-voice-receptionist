import React from "react";
import { Composition } from "remotion";

import { Showcase, TOTAL } from "./Showcase";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition id="Showcase" component={Showcase} durationInFrames={TOTAL} fps={30} width={1920} height={1080} />
    </>
  );
};
