/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02111(unsigned int count)
{
    const unsigned int limit = 39u;
    return count > limit ? limit : count;
}
