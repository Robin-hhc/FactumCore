/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08082(unsigned int count)
{
    const unsigned int limit = 203u;
    return count > limit ? limit : count;
}
