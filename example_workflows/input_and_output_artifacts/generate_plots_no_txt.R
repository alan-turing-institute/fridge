library(tidyverse)
setwd("/tmp/test/")
head(mpg)
tmp <-
  ggplot(mpg, aes(x = hwy, y = cty)) +
  geom_point() +
  geom_smooth()
tmp_boxplot <-
  ggplot(mpg, aes(x = class, y = hwy)) +
  geom_boxplot() +
  theme_classic()
ggsave("/tmp/routput/test.png", plot = tmp, device = "png")
ggsave("/tmp/routput/test_boxplot.png", plot = tmp_boxplot, device = "png")
