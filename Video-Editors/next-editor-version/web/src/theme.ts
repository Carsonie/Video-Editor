import { createTheme, type MantineColorsTuple } from '@mantine/core';

// The palette, taken from the players' own CSS rather than invented. The point
// of the rebuild is that it LOOKS like what it replaces, so these are the same
// hexes: #1a1a1a behind everything, #212629 panels, #353c42 borders, #cfd6dc
// text on a control and #8b949c on a label.
const panel: MantineColorsTuple = [
  '#eef1f3',
  '#cfd6dc',
  '#8b949c',
  '#7d858b',
  '#6d757b',
  '#4a5259',
  '#39424a',
  '#353c42',
  '#2c3236',
  '#212629',
];

// Break points are GREEN on an mp4 and PURPLE on a WebM — the same two colours
// the layered view uses for background and overlay. In the single-clip view
// there is no layer toggle to read, so the marks are the ONLY thing that can
// say which kind of file is open. Cutting Sarah is not cutting the screen
// recording, and the two are easy to confuse once a long avatar render is being
// spliced like any other clip.
const mark: MantineColorsTuple = [
  '#dff5e2', '#b6e9c0', '#9fe0ab', '#7ad48c', '#5aff70',
  '#2ecc40', '#25a334', '#1f5c2e', '#1f4a2e', '#173a22',
];

const alphaMark: MantineColorsTuple = [
  '#f0e8ff', '#dcc9ff', '#c9a3ff', '#b98cff', '#a56cff',
  '#8f4dff', '#7a35e6', '#5f2bb3', '#483571', '#3a2a5c',
];

export const theme = createTheme({
  primaryColor: 'panel',
  primaryShade: 5,
  colors: { panel, mark, alphaMark },
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  fontFamilyMonospace: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  defaultRadius: 'sm',
  components: {
    Button: {
      defaultProps: { variant: 'default', size: 'compact-sm' },
    },
    Tooltip: {
      // Every control in this tool carries a real explanation, several of them
      // a paragraph. A tooltip that clips them is worse than none.
      defaultProps: { multiline: true, w: 300, withArrow: true, openDelay: 350 },
    },
  },
});
