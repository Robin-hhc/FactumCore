/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04454(unsigned int count)
{
    const unsigned int limit = 30u;
    return count > limit ? limit : count;
}
