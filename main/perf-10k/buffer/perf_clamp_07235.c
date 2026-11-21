/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07235(unsigned int count)
{
    const unsigned int limit = 246u;
    return count > limit ? limit : count;
}
