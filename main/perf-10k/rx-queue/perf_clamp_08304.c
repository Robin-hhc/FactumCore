/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08304(unsigned int count)
{
    const unsigned int limit = 242u;
    return count > limit ? limit : count;
}
