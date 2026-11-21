/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02884(unsigned int count)
{
    const unsigned int limit = 232u;
    return count > limit ? limit : count;
}
