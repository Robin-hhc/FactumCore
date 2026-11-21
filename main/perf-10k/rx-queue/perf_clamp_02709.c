/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02709(unsigned int count)
{
    const unsigned int limit = 245u;
    return count > limit ? limit : count;
}
