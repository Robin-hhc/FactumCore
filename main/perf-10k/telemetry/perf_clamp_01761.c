/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01761(unsigned int count)
{
    const unsigned int limit = 65u;
    return count > limit ? limit : count;
}
