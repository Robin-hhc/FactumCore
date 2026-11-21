/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03264(unsigned int count)
{
    const unsigned int limit = 218u;
    return count > limit ? limit : count;
}
