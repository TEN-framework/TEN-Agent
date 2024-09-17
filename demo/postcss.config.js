module.exports = {
  plugins: {
    autoprefixer: {},
    "@minko-fe/postcss-pxtoviewport": {
      viewportWidth: 375,
      exclude: /node_modules/,
      include: /\/src\/platform\/mobile\//,
    }
  },
}
