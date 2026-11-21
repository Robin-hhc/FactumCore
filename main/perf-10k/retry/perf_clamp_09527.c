/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09527(unsigned int count)
{
    const unsigned int limit = 117u;
    return count > limit ? limit : count;
}
