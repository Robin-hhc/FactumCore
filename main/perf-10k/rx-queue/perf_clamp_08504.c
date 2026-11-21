/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08504(unsigned int count)
{
    const unsigned int limit = 156u;
    return count > limit ? limit : count;
}
