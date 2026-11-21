/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02054(unsigned int count)
{
    const unsigned int limit = 66u;
    return count > limit ? limit : count;
}
