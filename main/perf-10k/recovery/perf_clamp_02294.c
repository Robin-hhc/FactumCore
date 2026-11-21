/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02294(unsigned int count)
{
    const unsigned int limit = 162u;
    return count > limit ? limit : count;
}
